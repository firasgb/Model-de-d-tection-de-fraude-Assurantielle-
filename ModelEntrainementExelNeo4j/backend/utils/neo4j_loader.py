"""
Neo4j AuraDB Loader for PFE 2026
"""

import os
from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase, Driver, Session
from dotenv import load_dotenv

load_dotenv()

class PFE2026Neo4jLoader:
    """Chargeur de données Neo4j AuraDB"""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "neo4j+s://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.driver: Optional[Driver] = None
        
        if not self.password:
            print("⚠️  NEO4J_PASSWORD non définie")
            return
            
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_lifetime=3600,
                connection_acquisition_timeout=60
            )
            # Tester la connexion
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            print(f"✅ Neo4j AuraDB connecté: {self.uri}")
        except Exception as e:
            print(f"❌ Erreur connexion Neo4j: {e}")
            self.driver = None
    
    def get_session(self) -> Optional[Session]:
        if self.driver:
            return self.driver.session(database=self.database)
        return None
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict]:
        if not self.driver:
            return []
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    
    def test_connection(self) -> bool:
        """Test la connexion à Neo4j"""
        try:
            result = self.execute_query("RETURN datetime() as now")
            return len(result) > 0
        except Exception:
            return False