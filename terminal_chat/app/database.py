import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from .config import DB_PATH

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        model TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        style TEXT NOT NULL DEFAULT 'default',
        tags TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
    )
    ''')
    
    # Create indexes and full-text search
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversation_id ON messages (conversation_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations (created_at)')
    cursor.execute('CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, content=messages, content_rowid=id)')
    
    # Create FTS triggers
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
    END
    ''')
    
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
        INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
    END
    ''')
    
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    END
    ''')
    
    conn.commit()
    conn.close()

class ChatDatabase:
    def __init__(self):
        init_db()
        
    def _get_connection(self):
        """Get a database connection with row factory"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_conversation(self, title: str, model: str, style: str = "default", tags: List[str] = None) -> int:
        """Create a new conversation and return its ID"""
        now = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags) if tags else None
        
        cursor.execute(
            'INSERT INTO conversations (title, model, created_at, updated_at, style, tags) VALUES (?, ?, ?, ?, ?, ?)',
            (title, model, now, now, style, tags_json)
        )
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return conversation_id
    
    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        """Add a message to a conversation and return the message ID"""
        now = datetime.now().isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Add the message
        cursor.execute(
            'INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)',
            (conversation_id, role, content, now)
        )
        message_id = cursor.lastrowid
        
        # Update the conversation's updated_at timestamp
        cursor.execute(
            'UPDATE conversations SET updated_at = ? WHERE id = ?',
            (now, conversation_id)
        )
        
        conn.commit()
        conn.close()
        
        return message_id
    
    def get_conversation(self, conversation_id: int) -> Dict[str, Any]:
        """Get a conversation by ID, including all messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get conversation data
        cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
        conversation_row = cursor.fetchone()
        
        if not conversation_row:
            conn.close()
            return None
        
        conversation = dict(conversation_row)
        
        # Get all messages for this conversation
        cursor.execute('SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp', (conversation_id,))
        messages = [dict(row) for row in cursor.fetchall()]
        
        conversation['messages'] = messages
        
        # Parse tags if present
        if conversation['tags']:
            conversation['tags'] = json.loads(conversation['tags'])
        else:
            conversation['tags'] = []
            
        conn.close()
        return conversation
    
    def get_all_conversations(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all conversations with pagination"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ? OFFSET ?',
            (limit, offset)
        )
        
        conversations = []
        for row in cursor.fetchall():
            conversation = dict(row)
            if conversation['tags']:
                conversation['tags'] = json.loads(conversation['tags'])
            else:
                conversation['tags'] = []
                
            # Get message count
            cursor.execute(
                'SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?',
                (conversation['id'],)
            )
            count_row = cursor.fetchone()
            conversation['message_count'] = count_row['count']
            
            conversations.append(conversation)
            
        conn.close()
        return conversations
    
    def search_conversations(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for conversations containing the query in messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        results = []
        
        try:
            # First get matching message IDs using FTS
            cursor.execute('''
            SELECT DISTINCT conversation_id, content as matched_content
            FROM messages_fts
            JOIN messages ON messages_fts.rowid = messages.id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            ''', (query, limit))
            
            matching_messages = cursor.fetchall()
            if not matching_messages:
                return []
                
            # Get conversation IDs and their matched content
            conv_ids = [row[0] for row in matching_messages]
            matched_contents = {row[0]: row[1] for row in matching_messages}
            
            # Get conversation data efficiently
            placeholders = ','.join('?' * len(conv_ids))
            cursor.execute(f'''
            SELECT c.*, COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.id IN ({placeholders})
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            ''', conv_ids)
            
            for row in cursor.fetchall():
                conversation = dict(row)
                if conversation['tags']:
                    conversation['tags'] = json.loads(conversation['tags'])
                else:
                    conversation['tags'] = []
                    
                # Use the matched content from FTS results
                conversation['preview'] = matched_contents.get(conversation['id'], '')
                conversation['message_count'] = row['message_count']
                
                results.append(conversation)
                
        except sqlite3.Error as e:
            print(f"Database error during search: {e}")
        except Exception as e:
            print(f"Error during search: {e}")
        finally:
            conn.close()
            
        return results

    def update_conversation(self, conversation_id: int, title: str = None, tags: List[str] = None, style: str = None, model: str = None):
        """Update conversation metadata"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
            
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        
        if style is not None:
            updates.append("style = ?")
            params.append(style)
            
        if model is not None:
            updates.append("model = ?")
            params.append(model)
            
        if not updates:
            conn.close()
            return
            
        # Add updated_at
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        # Add conversation_id
        params.append(conversation_id)
        
        query = f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        
        conn.commit()
        conn.close()
    
    def delete_conversation(self, conversation_id: int):
        """Delete a conversation and all its messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Messages will be deleted via ON DELETE CASCADE
        cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
        
        conn.commit()
        conn.close()
