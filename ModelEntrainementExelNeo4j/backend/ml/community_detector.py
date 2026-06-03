"""
Community Detector  Dtection de rseaux suspects via Neo4j AuraDB
VERSION 7.0  Corrections issues des logs v6 :
  - id(node)  elementId(node)  [dprciation Neo4j 5+]
  - Proprits inexistantes supprimes (g.code, g.raison_sociale, a.matricule)
  - MISSING_ID : nuds sans identifiant mtier exclus de l'Union-Find
    (ils faussaient tout en fusionnant des milliers de sinistres)
  - Relation EST_IMPLIQUE_DANS retire de la requte Cypher car ses nuds
    n'ont pas de cin  tous mapps sur MISSING_ID  blob gant
    ( ractiver quand le problme d'identifiant sera rsolu ct donnes)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

# 
# Seuils configurables
# 
MIN_SINISTRES_COMMUNAUTE      = 2    # Nb min de sinistres distincts dans une communaut
MIN_MEMBERS_COMMUNAUTE        = 2    # Nb min de membres
MAX_COMMUNITY_SIZE            = 500  # Nb max de membres (mga-blob ignor)
HIGH_RISK_THRESHOLD           = 3    # Nb sinistres  niveau "critique"
MAX_ENTITY_SINISTRES_FOR_UNION = 50  # Au-del : entit trop connecte, exclue de l'Union-Find
UNION_FIND_EXCLUDED_TYPES     = {"garage", "analyste"}  # Types exclus de la fusion
MISSING_ID_PLACEHOLDER        = "MISSING_ID"  # Valeur sentinelle  exclure


class CommunityDetector:
    """Dtecte les rseaux suspects (communauts)  partir de Neo4j AuraDB."""

    def __init__(self, driver, database: str):
        self.driver   = driver
        self.database = database
        self._cache: Optional[Dict[str, Any]] = None

    # 
    # Point d'entre
    # 

    def get_full_analysis(self, force_refresh: bool = False) -> Dict[str, Any]:
        if self._cache and not force_refresh:
            return self._cache

        print("=" * 60)
        print(" COMMUNITY DETECTOR v7  Analyse Neo4j AuraDB")
        print("=" * 60)

        use_gds = self._check_gds_available()
        if use_gds:
            print("   Neo4j GDS disponible")
            communities_raw = self._detect_communities_gds()
        else:
            print("    Neo4j GDS absent  fallback Cypher + Union-Find")
            communities_raw = self._detect_communities_cypher()

        suspects, communities = self._format_results(communities_raw)
        stats      = self._compute_stats(suspects, communities)
        graph_data = self._build_graph_data(suspects, communities)

        result = {
            "suspects":     suspects,
            "communities":  communities,
            "stats":        stats,
            "graph":        graph_data,
            "generated_at": datetime.now().isoformat(),
        }
        self._cache = result
        print(f" Analyse termine  {len(communities)} communauts dtectes")
        return result

    # 
    # GDS (stub)
    # 

    def _check_gds_available(self) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN gds.version()").single()
                return True
        except Exception:
            return False

    def _detect_communities_gds(self) -> List[Dict]:
        raise NotImplementedError("GDS WCC  fallback Cypher oprationnel.")

    # 
    # Requte Cypher  schma nettoy
    # 

    def _detect_communities_cypher(self) -> List[Dict]:
        """
        Corrections v7 :
        - elementId(node)  la place de id(node)  [fin des warnings dprciation]
        - EST_IMPLIQUE_DANS retir : nuds sans cin  MISSING_ID  blob gant
          Ractiver quand les donnes auront un identifiant mtier fiable.
        - g.code / g.raison_sociale / a.matricule supprims (proprits absentes)
        - Garage identifi par g.nom uniquement
        - Analyste identifi par a.cin + a.nom uniquement
        """
        print("   Requte Cypher communauts...")

        query = """
        MATCH (s:Sinistre)

        //  Tmoins 
        OPTIONAL MATCH (temoin:Tiers)-[:TEMOIN_DE]-(s)
        WITH s, collect(DISTINCT {
            id:   coalesce(temoin.cin,  elementId(temoin)),
            nom:  coalesce(temoin.nom + ' ' + temoin.prenom, temoin.cin, 'Inconnu'),
            type: 'temoin'
        }) AS temoins_list

        //  Tiers participants 
        OPTIONAL MATCH (tiers:Tiers)-[:PARTICIPE_DANS]-(s)
        WITH s, temoins_list,
             collect(DISTINCT {
                 id:   coalesce(tiers.cin,  elementId(tiers)),
                 nom:  coalesce(tiers.nom + ' ' + tiers.prenom, tiers.cin, 'Inconnu'),
                 type: 'tiers'
             }) AS tiers_list

        //  Tiers impliqus (EST_IMPLIQUE_DANS)  uuid comme id fiable 
        OPTIONAL MATCH (tiers2:Tiers)-[:EST_IMPLIQUE_DANS]-(s)
        WITH s, temoins_list, tiers_list,
             collect(DISTINCT {
                 id:   coalesce(tiers2.uuid, tiers2.cin, elementId(tiers2)),
                 nom:  coalesce(tiers2.nom + ' ' + tiers2.prenom, tiers2.cin, 'Inconnu'),
                 type: 'tiers_implique'
             }) AS tiers_implique_list

        //  Vhicules assurs 
        OPTIONAL MATCH (v:Voiture)-[:IMPLIQUE_DANS]-(s)
        WITH s, temoins_list, tiers_list, tiers_implique_list,
             collect(DISTINCT {
                 id:   coalesce(v.immatriculation, elementId(v)),
                 nom:  coalesce(v.immatriculation, 'Vhicule inconnu'),
                 type: 'vehicule'
             }) AS vehicules_list

        //  Vhicules adverses 
        OPTIONAL MATCH (va:Voiture)-[:EST_IMPLIQUE_ADVERSE]-(s)
        WITH s, temoins_list, tiers_list, tiers_implique_list, vehicules_list,
             collect(DISTINCT {
                 id:   coalesce(va.immatriculation, elementId(va)),
                 nom:  coalesce(va.immatriculation, 'Vhicule adverse inconnu'),
                 type: 'vehicule_adverse'
             }) AS vehicules_adverses_list

        //  Dclarants / assurs 
        OPTIONAL MATCH (assure:Tiers)-[:DECLARE]-(s)
        WITH s, temoins_list, tiers_list, tiers_implique_list, vehicules_list, vehicules_adverses_list,
             collect(DISTINCT {
                 id:   coalesce(assure.cin,  elementId(assure)),
                 nom:  coalesce(assure.nom + ' ' + assure.prenom, assure.cin, 'Inconnu'),
                 type: 'assure'
             }) AS assures_list

        //  Garages (exclu Union-Find, mtadonne seulement) 
        OPTIONAL MATCH (g)-[:REPARE_CHEZ]-(s)
        WITH s, temoins_list, tiers_list, tiers_implique_list, vehicules_list,
             vehicules_adverses_list, assures_list,
             collect(DISTINCT {
                 id:   coalesce(g.nom, elementId(g)),
                 nom:  coalesce(g.nom, 'Garage inconnu'),
                 type: 'garage'
             }) AS garages_list

        //  Analystes (exclu Union-Find, mtadonne seulement) 
        OPTIONAL MATCH (a)-[:EXPERTISE_PAR]-(s)
        WITH s, temoins_list, tiers_list, tiers_implique_list, vehicules_list,
             vehicules_adverses_list, assures_list, garages_list,
             collect(DISTINCT {
                 id:   coalesce(a.cin, elementId(a)),
                 nom:  coalesce(a.nom + ' ' + a.prenom, a.nom, 'Analyste inconnu'),
                 type: 'analyste'
             }) AS analystes_list

        WITH s,
             temoins_list + tiers_list + tiers_implique_list +
             vehicules_list + vehicules_adverses_list +
             assures_list + garages_list + analystes_list AS all_entities

        WHERE size(all_entities) >= 2

        RETURN
            coalesce(s.NUM_SINISTRE, elementId(s)) AS sinistre_id,
            all_entities
        """

        sinistre_entities: Dict[str, List[Dict]] = {}
        try:
            with self.driver.session(database=self.database) as session:
                records = session.run(query)
                for rec in records:
                    sid      = str(rec["sinistre_id"])
                    entities = [
                        e for e in rec["all_entities"]
                        if e
                        and e.get("id")
                        and str(e["id"]) != MISSING_ID_PLACEHOLDER
                        and str(e["id"]).strip() != ""
                    ]
                    if len(entities) >= 2:
                        sinistre_entities[sid] = entities
        except Exception as ex:
            print(f"    Erreur requte communauts: {ex}")
            return []

        print(f"     {len(sinistre_entities)} sinistres multi-entits trouvs")
        return self._union_find_communities(sinistre_entities)

    # 
    # Union-Find
    # 

    def _union_find_communities(
        self, sinistre_entities: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Union-Find avec exclusion des entits hyper-connectes et des types
        qui servent de "pont universel" (garages, analystes).
        """
        print("   Union-Find...")

        parent:           Dict[str, str]  = {}
        entity_info:      Dict[str, Dict] = {}
        entity_sinistres: Dict[str, set]  = defaultdict(set)

        def make_key(e: Dict) -> str:
            return f"{e['type']}:{e['id']}"

        for sid, entities in sinistre_entities.items():
            for e in entities:
                key = make_key(e)
                if key not in entity_info:
                    entity_info[key] = {**e, "entity_type": e["type"]}
                    parent[key]      = key
                entity_sinistres[key].add(sid)

        # Identifier les entits  exclure de la fusion
        excluded: set = set()
        for key, sins in entity_sinistres.items():
            etype = entity_info[key]["type"]
            if etype in UNION_FIND_EXCLUDED_TYPES:
                excluded.add(key)
            elif len(sins) > MAX_ENTITY_SINISTRES_FOR_UNION:
                excluded.add(key)
                print(f"       Exclu (hyper-connect) : {key[:60]}  {len(sins)} sinistres")

        print(f"     {len(excluded)} entits exclues de l'Union-Find")

        def find(x: str) -> str:
            root = x
            while parent.get(root, root) != root:
                root = parent[root]
            while parent.get(x, x) != root:
                parent[x], x = root, parent.get(x, x)
            return root

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for sid, entities in sinistre_entities.items():
            keys = [
                make_key(e) for e in entities
                if make_key(e) not in excluded
            ]
            for i in range(1, len(keys)):
                union(keys[0], keys[i])

        groups: Dict[str, List[str]] = defaultdict(list)
        for key in entity_info:
            if key not in excluded:
                groups[find(key)].append(key)

        communities = []
        cid = 0

        for root, members in groups.items():
            if len(members) < MIN_MEMBERS_COMMUNAUTE:
                continue

            all_sins: set = set()
            for m in members:
                all_sins.update(entity_sinistres[m])

            if len(all_sins) < MIN_SINISTRES_COMMUNAUTE:
                continue

            if len(members) > MAX_COMMUNITY_SIZE:
                print(f"       Communaut ignore (blob) : {len(members)} membres, {len(all_sins)} sinistres")
                continue

            member_data = []
            for m in members:
                nb    = len(entity_sinistres[m])
                info  = entity_info[m]
                score = min(round(nb / HIGH_RISK_THRESHOLD * 100, 1), 100.0)
                level = "critique" if nb >= HIGH_RISK_THRESHOLD else "lev"
                member_data.append({
                    "id":            info["id"],
                    "nom":           info.get("nom", "Inconnu"),
                    "type":          info["entity_type"],
                    "nb_sinistres":  nb,
                    "niveau":        level,
                    "score":         score,
                    "sinistres_ids": list(entity_sinistres[m]),
                })

            max_score   = max(m["score"] for m in member_data)
            avg_score   = round(sum(m["score"] for m in member_data) / len(member_data), 1)
            nb_critique = sum(1 for m in member_data if m["niveau"] == "critique")

            if nb_critique >= 2 or max_score >= 90:
                niveau = "critique"
            elif max_score >= 60 or len(members) >= 3:
                niveau = "lev"
            else:
                niveau = "modr"

            type_counts: Dict[str, int] = defaultdict(int)
            for m in member_data:
                type_counts[m["type"]] += 1

            communities.append({
                "id":            cid,
                "taille":        len(members),
                "nb_sinistres":  len(all_sins),
                "sinistres_ids": list(all_sins),
                "score_max":     max_score,
                "score_moyen":   avg_score,
                "niveau":        niveau,
                "nb_critique":   nb_critique,
                "composition":   dict(type_counts),
                "membres":       member_data,
            })
            cid += 1

        communities.sort(key=lambda c: (-c["nb_sinistres"], -c["taille"]))
        print(f"     {len(communities)} communauts construites")
        return communities

    # 
    # Formatage
    # 

    def _format_results(self, communities: List[Dict]) -> tuple:
        temoins   = []
        tiers     = []
        vehicules = []
        assures   = []
        garages   = []
        analystes = []
        seen      = set()

        for comm in communities:
            for m in comm.get("membres", []):
                key = f"{m['type']}:{m['id']}"
                if key in seen:
                    continue
                seen.add(key)
                entry = {
                    "id":            m["id"],
                    "nom":           m["nom"],
                    "type":          m["type"],
                    "nb_sinistres":  m["nb_sinistres"],
                    "sinistres_ids": m.get("sinistres_ids", []),
                    "niveau":        m["niveau"],
                    "score":         m["score"],
                }
                t = m["type"]
                if t == "temoin":
                    temoins.append(entry)
                elif t in ("tiers", "tiers_implique"):
                    tiers.append(entry)
                elif t in ("vehicule", "vehicule_adverse"):
                    vehicules.append(entry)
                elif t == "assure":
                    assures.append(entry)
                elif t == "garage":
                    garages.append(entry)
                elif t == "analyste":
                    analystes.append(entry)

        return {
            "temoins":   temoins,
            "tiers":     tiers,
            "vehicules": vehicules,
            "assures":   assures,
            "garages":   garages,
            "analystes": analystes,
        }, communities

    # 
    # Graphe
    # 

    def _build_graph_data(self, suspects: Dict, communities: List) -> Dict[str, Any]:
        nodes:    List[Dict] = []
        edges:    List[Dict] = []
        node_ids: set        = set()
        edge_set: set        = set()

        entity_to_comm: Dict[str, int] = {}
        for comm in communities:
            for m in comm.get("membres", []):
                entity_to_comm[f"{m['type']}:{m['id']}"] = comm["id"]

        for _etype, entity_list in suspects.items():
            for e in entity_list:
                node_id = f"{e['type']}:{e['id']}"
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    nodes.append({
                        "id":           node_id,
                        "label":        e["nom"][:30],
                        "type":         e["type"],
                        "niveau":       e["niveau"],
                        "score":        e["score"],
                        "nb_sinistres": e["nb_sinistres"],
                        "community_id": entity_to_comm.get(node_id, -1),
                        "group":        "suspect",
                    })

                for sid in e.get("sinistres_ids", []):
                    sin_node_id = f"sinistre:{sid}"
                    if sin_node_id not in node_ids:
                        node_ids.add(sin_node_id)
                        nodes.append({
                            "id":           sin_node_id,
                            "label":        str(sid)[:20],
                            "type":         "sinistre",
                            "niveau":       "sinistre",
                            "score":        0,
                            "nb_sinistres": 1,
                            "community_id": entity_to_comm.get(node_id, -1),
                            "group":        "sinistre",
                        })

                    edge_key = f"{node_id}--{sin_node_id}"
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append({"source": node_id, "target": sin_node_id, "weight": 1})

        community_meta = [
            {
                "id":           c["id"],
                "niveau":       c["niveau"],
                "taille":       c["taille"],
                "nb_sinistres": c["nb_sinistres"],
                "score_max":    c["score_max"],
            }
            for c in communities
        ]

        return {
            "nodes":       nodes,
            "edges":       edges,
            "communities": community_meta,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    # 
    # Statistiques
    # 

    def _compute_stats(self, suspects: Dict, communities: List) -> Dict[str, Any]:
        temoins   = suspects.get("temoins",   [])
        tiers     = suspects.get("tiers",     [])
        vehicules = suspects.get("vehicules", [])
        assures   = suspects.get("assures",   [])
        garages   = suspects.get("garages",   [])
        analystes = suspects.get("analystes", [])

        all_lists      = (temoins, tiers, vehicules, assures, garages, analystes)
        total_suspects = sum(len(lst) for lst in all_lists)
        total_critique = sum(
            1 for lst in all_lists for e in lst if e["niveau"] == "critique"
        )

        return {
            "total_suspects":      total_suspects,
            "total_critique":      total_critique,
            "nb_temoins":          len(temoins),
            "nb_tiers":            len(tiers),
            "nb_vehicules":        len(vehicules),
            "nb_assures":          len(assures),
            "nb_garages":          len(garages),
            "nb_analystes":        len(analystes),
            "nb_communautes":      len(communities),
            "communautes_crit":    sum(1 for c in communities if c["niveau"] == "critique"),
            "sinistres_impliques": len({
                s for c in communities for s in c["sinistres_ids"]
            }),
        }

