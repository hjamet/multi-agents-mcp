import sys
import os
import uuid

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from src.core.state import StateStore

def setup_werewolf():
    store = StateStore()
    
    def update_logic(state):
        # 1. Clear State
        state["conversation_id"] = str(uuid.uuid4())
        state["messages"] = []
        state["turn"] = {"current": None, "next": None}
        
        # 2. Global Context
        state.setdefault("config", {})["context"] = (
            "Nous jouons au Loup-Garou de Thiercelieux. "
            "C'est la Nuit. Tous le monde dort. "
            "Le MJ (Maitre du Jeu) va orchestrer les tours. "
            "Les Loups doivent se mettre d'accord pour tuer un Villageois. "
            "Les Villageois dorment et ne savent rien."
        )
        
        profiles = []
        
        # 3. Create Profiles
        
        # MJ
        profiles.append({
            "name": "MaitreDuJeu",
            "description": "Orchestre la partie",
            "system_prompt": "Tu es le Maitre du Jeu. Tu diriges la partie. Tu appelles les rôles la nuit.",
            "capabilities": ["public", "private", "audience", "open"], # MJ sees all
            "connections": [],
            "count": 1
        })
        
        # Villager (Simple)
        profiles.append({
            "name": "Villageois",
            "description": "Un habitant innocent",
            "system_prompt": "Tu es un simple Villageois. Tu dors la nuit. Tu as peur.",
            "capabilities": ["public", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Obéis au MJ."}
            ],
            "count": 7 
        })
        
        # Loup-Garou
        profiles.append({
            "name": "LoupGarou",
            "description": "Prédateur nocturne",
            "system_prompt": "Tu es un Loup-Garou. Tu dois tuer les villageois sans te faire repérer.",
            "capabilities": ["public", "private", "audience"],
            "connections": [
                {"target": "MaitreDuJeu", "context": "Obéis au MJ."},
                {"target": "LoupGarou", "context": "C'est ton allié. Coopère pour choisir une victime commune."}
            ],
            "count": 3
        })
        
        state["config"]["profiles"] = profiles
        state["config"]["total_agents"] = 11
        
        # 4. Create Agents Instances (Names: Marc, Sophie, etc)
        # We need specific names for immersion, but `app.py` currently generates `Name_X`.
        # To support "Marc", "Sophie", we would need a 'Names' list in profile or manual rename.
        # For now, let's stick to standard `LoupGarou_1` to ensure the Logic (profile matching) works reliably 
        # without complex name resolution in logic.py yet.
        # Wait, user asked for "Marc", "Sophie". 
        # Refactor idea: Logic currently resolves `Sender -> Sender Profile` via `profile_ref`.
        # So the ID key in `agents` dict DOES NOT need to match Profile Name.
        # It just needs `profile_ref`.
        
        names_pool = ["Marc", "Sophie", "Antoine", "Julie", "Pierre", "Marie", "Luc", "Thomas", "Emma", "Chloe"]
        # 7 Villagers + 3 Wolves = 10 Players
        
        new_agents = {}
        
        # MJ
        new_agents["MaitreDuJeu"] = {
            "role": profiles[0]["system_prompt"],
            "status": "pending_connection",
            "profile_ref": "MaitreDuJeu"
        }
        
        # Assignment
        import random
        random.shuffle(names_pool)
        
        # 3 Wolves
        for i in range(3):
            name = names_pool.pop()
            # We must map "LoupGarou" connections to real names? 
            # Current Logic: `allowed_targets` uses Profile Names (e.g. key="LoupGarou").
            # The check `check_target` takes target_name (e.g. "Pierre"), finds its profile ("LoupGarou") 
            # and checks if "LoupGarou" is in allowed.
            # So YES, we can use custom names!
            
            p = profiles[2] # Loup
            new_agents[name] = {
                "role": p["system_prompt"],
                "status": "pending_connection",
                "profile_ref": "LoupGarou"
            }
            
        # 7 Villagers
        for i in range(7):
            name = names_pool.pop()
            p = profiles[1] # Villager
            new_agents[name] = {
                "role": p["system_prompt"],
                "status": "pending_connection",
                "profile_ref": "Villageois"
            }
            
        state["agents"] = new_agents
        
        return "Werewolf Setup Complete"

    msg = store.update(update_logic)
    print(msg)

if __name__ == "__main__":
    setup_werewolf()
