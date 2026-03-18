from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class Neo4jConnection:
    """Simple Neo4j connection wrapper."""

    def __init__(self):
        self._driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

    def close(self):
        self._driver.close()

    def run(self, query: str, params: dict = None):
        with self._driver.session() as session:
            result = session.run(query, params or {})
            return result.data()

    def verify(self):
        try:
            self._driver.verify_connectivity()
            print(f"[neo4j] Connected to {NEO4J_URI}")
            return True
        except Exception as e:
            print(f"[neo4j] Connection failed: {e}")
            return False