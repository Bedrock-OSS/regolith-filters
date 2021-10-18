from reticulator import *

def fetch_name(entity: EntityFileBP):
    entity.get_data_at('minecraft:entity.description.identifier', entity.data)

def main():
    behavior_pack = BehaviorPack("./BP")

    for entity in behavior_pack.entities:
        print(entity.identifier)

if __name__ == "__main__":
    main()