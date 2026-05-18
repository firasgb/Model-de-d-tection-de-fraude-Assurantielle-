"""
Community Detector — Détection de réseaux suspects via Neo4j AuraDB
VERSION 2.0 — avec export de données graphe pour visualisation
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

# Seuils configurables
MIN_SINISTRES_SUSPECT = 2
HIGH_RISK_THRESHOLD = 3
COMMUNITY_MIN_SIZE = 2


class CommunityDetector:
    """Détecte les réseaux suspects (communautés) à partir de Neo4j AuraDB"""

    def __init__(self, driver, database: str):
        self.driver = driver
        self.database = database
        self._cache: Optional[Dict[str, Any]] = None

    def get_full_analysis(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Lance toute l'analyse et retourne un dict structuré"""
        if self._cache and not force_refresh:
            return self._cache

        print("=" * 50)
        print("🔍 COMMUNITY DETECTOR — Analyse Neo4j AuraDB")
        print("=" * 50)

        temoins = self._analyze_temoins()
        tiers = self._analyze_tiers()
        vehicules = self._analyze_vehicules()
        assures = self._analyze_assures()

        communities = self._build_communities(temoins, tiers, vehicules, assures)
        stats = self._compute_stats(temoins, tiers, vehicules, assures, communities)
        graph_data = self._build_graph_data(temoins, tiers, vehicules, assures, communities)

        result = {
            "suspects": {
                "temoins": temoins,
                "tiers": tiers,
                "vehicules": vehicules,
                "assures": assures,
            },
            "communities": communities,
            "stats": stats,
            "graph": graph_data,
            "generated_at": datetime.now().isoformat(),
        }
        self._cache = result
        print(f"✅ Analyse terminée — {len(communities)} communautés détectées")
        return result

    def _analyze_temoins(self) -> List[Dict[str, Any]]:
        print("  → Analyse témoins...")
        query = """
        MATCH (temoin:Tiers)-[:TEMOIN_DE]->(s:Sinistre)
        WITH temoin, count(DISTINCT s) AS nb_sinistres,
             collect(DISTINCT coalesce(s.NUM_SINISTRE, toString(id(s)))) AS sinistres_ids
        WHERE nb_sinistres >= $min_sin
        RETURN
            coalesce(temoin.cin, toString(id(temoin))) AS id,
            coalesce(temoin.nom + ' ' + temoin.prenom, temoin.cin, 'Inconnu') AS nom,
            nb_sinistres,
            sinistres_ids
        ORDER BY nb_sinistres DESC
        """
        return self._run_suspect_query(query, "temoin")

    def _analyze_tiers(self) -> List[Dict[str, Any]]:
        print("  → Analyse tiers...")
        query = """
        MATCH (t:Tiers)-[:PARTICIPE_DANS]->(s:Sinistre)
        WITH t, count(DISTINCT s) AS nb_sinistres,
             collect(DISTINCT coalesce(s.NUM_SINISTRE, toString(id(s)))) AS sinistres_ids
        WHERE nb_sinistres >= $min_sin
        RETURN
            coalesce(t.cin, toString(id(t))) AS id,
            coalesce(t.nom + ' ' + t.prenom, t.cin, 'Inconnu') AS nom,
            nb_sinistres,
            sinistres_ids
        ORDER BY nb_sinistres DESC
        """
        return self._run_suspect_query(query, "tiers")

    def _analyze_vehicules(self) -> List[Dict[str, Any]]:
        print("  → Analyse véhicules...")
        query = """
        MATCH (v:Voiture)-[:IMPLIQUE_DANS]->(s:Sinistre)
        WITH v, count(DISTINCT s) AS nb_sinistres,
             collect(DISTINCT coalesce(s.NUM_SINISTRE, toString(id(s)))) AS sinistres_ids
        WHERE nb_sinistres >= $min_sin
        RETURN
            coalesce(v.immatriculation, toString(id(v))) AS id,
            coalesce(v.immatriculation, 'Véhicule inconnu') AS nom,
            nb_sinistres,
            sinistres_ids
        ORDER BY nb_sinistres DESC
        """
        return self._run_suspect_query(query, "vehicule")

    def _analyze_assures(self) -> List[Dict[str, Any]]:
        print("  → Analyse assurés...")
        query = """
        MATCH (t:Tiers)-[:DECLARE]->(s:Sinistre)
        WITH t, count(DISTINCT s) AS nb_sinistres,
             collect(DISTINCT coalesce(s.NUM_SINISTRE, toString(id(s)))) AS sinistres_ids
        WHERE nb_sinistres >= $min_sin
        RETURN
            coalesce(t.cin, toString(id(t))) AS id,
            coalesce(t.nom + ' ' + t.prenom, t.cin, 'Inconnu') AS nom,
            nb_sinistres,
            sinistres_ids
        ORDER BY nb_sinistres DESC
        """
        return self._run_suspect_query(query, "assure")

    def _run_suspect_query(self, query: str, entity_type: str) -> List[Dict[str, Any]]:
        results = []
        try:
            with self.driver.session(database=self.database) as session:
                records = session.run(query, min_sin=MIN_SINISTRES_SUSPECT)
                for rec in records:
                    nb = int(rec["nb_sinistres"])
                    results.append({
                        "id": rec["id"],
                        "nom": rec["nom"],
                        "type": entity_type,
                        "nb_sinistres": nb,
                        "sinistres_ids": list(rec["sinistres_ids"])[:20],
                        "niveau": "critique" if nb >= HIGH_RISK_THRESHOLD else "élevé",
                        "score": min(round(nb / HIGH_RISK_THRESHOLD * 100, 1), 100.0),
                    })
            print(f"     {len(results)} {entity_type}(s) suspect(s)")
        except Exception as e:
            print(f"     ⚠️ Erreur query {entity_type}: {e}")
        return results

    def _build_communities(self, temoins: List, tiers: List, vehicules: List, assures: List) -> List[Dict[str, Any]]:
        """Regroupe les entités suspectes qui partagent des sinistres communs"""
        print("  → Construction des communautés...")

        all_suspects = (
            [(e, "temoin") for e in temoins] +
            [(e, "tiers") for e in tiers] +
            [(e, "vehicule") for e in vehicules] +
            [(e, "assure") for e in assures]
        )

        if not all_suspects:
            return []

        sin_to_entities: Dict[str, List[str]] = defaultdict(list)
        entity_info: Dict[str, Dict] = {}

        for entity, etype in all_suspects:
            eid = f"{etype}:{entity['id']}"
            entity_info[eid] = {**entity, "entity_type": etype}
            for sin_id in entity["sinistres_ids"]:
                sin_to_entities[str(sin_id)].append(eid)

        parent: Dict[str, str] = {eid: eid for eid in entity_info}

        # ─── CORRECTION : find() protégé contre KeyError ─────────────────────
        def find(x: str) -> str:
            if x not in parent:
                parent[x] = x
            # Compression de chemin
            while parent[x] != x:
                if parent[x] not in parent:
                    parent[parent[x]] = parent[x]
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for _, eids in sin_to_entities.items():
            for i in range(1, len(eids)):
                union(eids[0], eids[i])

        groups: Dict[str, List[str]] = defaultdict(list)
        for eid in entity_info:
            groups[find(eid)].append(eid)

        communities = []
        cid = 0
        for root, members in groups.items():
            if len(members) < COMMUNITY_MIN_SIZE:
                continue

            all_sins: set = set()
            for m in members:
                all_sins.update(entity_info[m]["sinistres_ids"])

            max_score = max(entity_info[m]["score"] for m in members)
            avg_score = round(sum(entity_info[m]["score"] for m in members) / len(members), 1)
            nb_critique = sum(1 for m in members if entity_info[m]["niveau"] == "critique")

            if nb_critique >= 2 or max_score >= 90:
                niveau = "critique"
            elif max_score >= 60 or len(members) >= 3:
                niveau = "élevé"
            else:
                niveau = "modéré"

            type_counts: Dict[str, int] = defaultdict(int)
            for m in members:
                type_counts[entity_info[m]["entity_type"]] += 1

            communities.append({
                "id": cid,
                "taille": len(members),
                "nb_sinistres": len(all_sins),
                "sinistres_ids": list(all_sins)[:30],
                "score_max": max_score,
                "score_moyen": avg_score,
                "niveau": niveau,
                "nb_critique": nb_critique,
                "composition": dict(type_counts),
                "membres": [
                    {
                        "id": entity_info[m]["id"],
                        "nom": entity_info[m]["nom"],
                        "type": entity_info[m]["entity_type"],
                        "nb_sinistres": entity_info[m]["nb_sinistres"],
                        "niveau": entity_info[m]["niveau"],
                        "score": entity_info[m]["score"],
                    }
                    for m in members
                ],
            })
            cid += 1

        communities.sort(key=lambda c: (-c["score_max"], -c["taille"]))
        print(f"     {len(communities)} communautés construites")
        return communities

    def _build_graph_data(
        self,
        temoins: List,
        tiers: List,
        vehicules: List,
        assures: List,
        communities: List,
    ) -> Dict[str, Any]:
        """
        Construit les données de graphe (nodes + edges) pour la visualisation frontend.
        Inclut les entités suspectes ET les sinistres comme nœuds intermédiaires.
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids: set = set()

        # Map sinistre_id → community_id
        sin_to_comm: Dict[str, int] = {}
        for comm in communities:
            for sid in comm.get("sinistres_ids", []):
                sin_to_comm[str(sid)] = comm["id"]

        # Map entity_id → community_id
        entity_to_comm: Dict[str, int] = {}
        for comm in communities:
            for m in comm.get("membres", []):
                eid = f"{m['type']}:{m['id']}"
                entity_to_comm[eid] = comm["id"]

        # Ajouter nœuds entités suspectes
        for entity_list, etype in [
            (temoins, "temoin"),
            (tiers, "tiers"),
            (vehicules, "vehicule"),
            (assures, "assure"),
        ]:
            for e in entity_list:
                node_id = f"{etype}:{e['id']}"
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    nodes.append({
                        "id": node_id,
                        "label": e["nom"][:30],
                        "type": etype,
                        "niveau": e["niveau"],
                        "score": e["score"],
                        "nb_sinistres": e["nb_sinistres"],
                        "community_id": entity_to_comm.get(node_id, -1),
                        "group": "suspect",
                    })

        # Ajouter nœuds sinistres (comme hubs)
        all_sin_ids: set = set()
        for entity_list in [temoins, tiers, vehicules, assures]:
            for e in entity_list:
                for sid in e.get("sinistres_ids", []):
                    all_sin_ids.add(str(sid))

        for sid in all_sin_ids:
            sin_node_id = f"sinistre:{sid}"
            if sin_node_id not in node_ids:
                node_ids.add(sin_node_id)
                comm_id = sin_to_comm.get(sid, -1)
                nodes.append({
                    "id": sin_node_id,
                    "label": sid[:20],
                    "type": "sinistre",
                    "niveau": "sinistre",
                    "score": 0,
                    "nb_sinistres": 1,
                    "community_id": comm_id,
                    "group": "sinistre",
                })

        # Ajouter liens entité → sinistre
        edge_set: set = set()
        for entity_list, etype in [
            (temoins, "temoin"),
            (tiers, "tiers"),
            (vehicules, "vehicule"),
            (assures, "assure"),
        ]:
            for e in entity_list:
                src = f"{etype}:{e['id']}"
                for sid in e.get("sinistres_ids", []):
                    dst = f"sinistre:{sid}"
                    edge_key = f"{src}--{dst}"
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append({
                            "source": src,
                            "target": dst,
                            "weight": 1,
                        })

        # Communautés résumées pour légende/filtre
        community_meta = [
            {
                "id": c["id"],
                "niveau": c["niveau"],
                "taille": c["taille"],
                "nb_sinistres": c["nb_sinistres"],
                "score_max": c["score_max"],
            }
            for c in communities
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "communities": community_meta,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    def _compute_stats(self, temoins: List, tiers: List, vehicules: List, assures: List, communities: List) -> Dict[str, Any]:
        total_suspects = len(temoins) + len(tiers) + len(vehicules) + len(assures)
        total_critique = sum(
            1 for lst in (temoins, tiers, vehicules, assures)
            for e in lst if e["niveau"] == "critique"
        )
        return {
            "total_suspects": total_suspects,
            "total_critique": total_critique,
            "nb_temoins": len(temoins),
            "nb_tiers": len(tiers),
            "nb_vehicules": len(vehicules),
            "nb_assures": len(assures),
            "nb_communautes": len(communities),
            "communautes_crit": sum(1 for c in communities if c["niveau"] == "critique"),
            "sinistres_impliques": len({
                s for c in communities for s in c["sinistres_ids"]
            }),
        }