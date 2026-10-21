"""Seed script for greenhouse-agent Firestore database."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-63b2ade03132"
COLLECTION_NAME = "plants"

SAMPLE_PLANTS = [
    {
        "id": "monstera-deliciosa",
        "name": "Monstera Deliciosa",
        "species": "Monstera deliciosa",
        "care_level": "Easy",
        "light": "Bright indirect light",
        "watering": "Every 1-2 weeks when top 2 inches of soil are dry",
        "price": 35.00,
        "stock": 15,
        "description": "Popular tropical houseplant with iconic Swiss-cheese split leaves.",
    },
    {
        "id": "fiddle-leaf-fig",
        "name": "Fiddle Leaf Fig",
        "species": "Ficus lyrata",
        "care_level": "Moderate",
        "light": "Bright filtered light; avoid direct midday sun",
        "watering": "Weekly when top inch of soil dries out",
        "price": 45.00,
        "stock": 8,
        "description": "Stunning statement plant with large, glossy violin-shaped foliage.",
    },
    {
        "id": "snake-plant",
        "name": "Snake Plant",
        "species": "Sansevieria trifasciata",
        "care_level": "Easy",
        "light": "Low to bright indirect light; very adaptable",
        "watering": "Every 2-3 weeks; allow soil to dry completely",
        "price": 24.00,
        "stock": 20,
        "description": "Hardy, air-purifying architectural plant that thrives on neglect.",
    },
    {
        "id": "golden-pothos",
        "name": "Golden Pothos",
        "species": "Epipremnum aureum",
        "care_level": "Easy",
        "light": "Low to medium indirect light",
        "watering": "Every 1-2 weeks when soil is dry to the touch",
        "price": 18.00,
        "stock": 25,
        "description": "Fast-growing trailing vine with vibrant green and gold variegated leaves.",
    },
    {
        "id": "peace-lily",
        "name": "Peace Lily",
        "species": "Spathiphyllum",
        "care_level": "Moderate",
        "light": "Medium to low indirect light",
        "watering": "Weekly; visibly droops when thirsty and perks up after watering",
        "price": 28.00,
        "stock": 10,
        "description": "Elegant flowering houseplant known for air purification and white blooms.",
    },
    {
        "id": "calathea-orbifolia",
        "name": "Calathea Orbifolia",
        "species": "Calathea orbifolia",
        "care_level": "Expert",
        "light": "Medium to bright indirect light; high humidity",
        "watering": "Twice weekly; keep soil consistently moist with filtered water",
        "price": 38.00,
        "stock": 6,
        "description": "Showstopper prayer plant featuring oversized round leaves with silver stripes.",
    },
]


def seed_database():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    for plant in SAMPLE_PLANTS:
        doc_id = plant["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(plant)
        print(f"Seeded: {plant['name']} (ID: {doc_id})")

    print(f"Successfully seeded {len(SAMPLE_PLANTS)} plants into '{COLLECTION_NAME}' collection!")


if __name__ == "__main__":
    seed_database()
