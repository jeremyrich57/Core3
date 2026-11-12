/*
				Copyright <SWGEmu>
		See file COPYING for copying conditions.*/

#ifndef VEHICLETESTKIT_H_
#define VEHICLETESTKIT_H_

#include "ArmorTestKit.h"

/**
 * Staff test kits for the AotC vehicles. Each gives the vehicle's loot schematic (5 uses), max-quality metals and a
 * stack of Specialized Speeder Power Plants for those 5 crafts, and one max-quality crafted deed.
 *   /object barckit  - BARC Speeder
 *   /object stapkit  - STAP Speeder
 * With a player targeted, the kit goes to that player's inventory instead of yours.
 */
class VehicleTestKit {
	static void give(ZoneServer* zoneServer, CreatureObject* staff, CreatureObject* recipient, const String& kitName,
			const char* lootSchematic, const char* draftSchematic) {
		const ArmorTestKit::KitComponent items[] = {
			{lootSchematic, 1},
			{"object/tangible/component/vehicle/veh_power_plant.iff", 5},
		};
		const int itemCount = sizeof(items) / sizeof(items[0]);

		// Both schematics take 1125 non-ferrous and 3125 ferrous metal per craft
		static const ArmorTestKit::KitResource resources[] = {
			{"metal_nonferrous", 1125 * 5},
			{"metal_ferrous", 3125 * 5},
		};
		const int resourceCount = sizeof(resources) / sizeof(resources[0]);

		ManagedReference<SceneObject*> inventory = recipient->getSlottedObject("inventory");
		ManagedReference<ResourceManager*> resourceManager = zoneServer->getResourceManager();

		if (inventory == nullptr || resourceManager == nullptr)
			return;

		if (!ArmorTestKit::checkRoom(staff, inventory, itemCount + resourceCount + 1, kitName))
			return;

		const int resourcesGiven = ArmorTestKit::giveResources(resourceManager, recipient, inventory, resources, resourceCount, kitName);
		const int itemsGiven = ArmorTestKit::giveItems(zoneServer, recipient, inventory, items, itemCount, kitName);

		bool deedGiven = false;
		ManagedReference<TangibleObject*> deed = ArmorTestKit::craftMaxQuality(zoneServer, recipient, draftSchematic, kitName);

		if (deed != nullptr) {
			Locker deedLocker(deed, recipient);

			if (inventory->transferObject(deed, -1, true)) {
				inventory->broadcastObject(deed, true);
				deedGiven = true;
			} else {
				deed->destroyObjectFromDatabase(true);
			}
		}

		const String summary = kitName + ": " + String::valueOf(resourcesGiven) + "/" + String::valueOf(resourceCount)
				+ " max-quality metals, " + String::valueOf(itemsGiven) + "/" + String::valueOf(itemCount)
				+ " items (loot schematic, 5 power plants) and " + (deedGiven ? "a" : "no") + " max-quality deed added";

		recipient->sendSystemMessage(summary + ".");

		if (staff != recipient)
			staff->sendSystemMessage(summary + " to " + recipient->getFirstName() + ".");

		staff->info(true) << "/object " << kitName << " given to " << recipient->getFirstName() << " by " << staff->getFirstName();
	}

public:
	// Returns false if commandType isn't a vehicle kit.
	static bool handle(ZoneServer* zoneServer, CreatureObject* staff, uint64 target, const String& commandType) {
		const char* lootSchematic = nullptr;
		const char* draftSchematic = nullptr;
		String kitName;

		if (commandType == "barckit") {
			kitName = "BARC Speeder kit";
			lootSchematic = "object/tangible/loot/loot_schematic/barc_speeder_schematic.iff";
			draftSchematic = "object/draft_schematic/vehicle/civilian/barc_speeder.iff";
		} else if (commandType == "stapkit") {
			kitName = "STAP Speeder kit";
			lootSchematic = "object/tangible/loot/loot_schematic/speeder_stap_schematic.iff";
			draftSchematic = "object/draft_schematic/vehicle/civilian/speeder_stap.iff";
		} else {
			return false;
		}

		ManagedReference<SceneObject*> targetObject = zoneServer->getObject(target);
		ManagedReference<CreatureObject*> recipient = staff;

		if (targetObject != nullptr && targetObject != staff && targetObject->isPlayerCreature())
			recipient = targetObject->asCreatureObject();

		if (recipient == staff) {
			give(zoneServer, staff, staff, kitName, lootSchematic, draftSchematic);
		} else {
			Locker clocker(recipient, staff);
			give(zoneServer, staff, recipient, kitName, lootSchematic, draftSchematic);
		}

		return true;
	}
};

#endif // VEHICLETESTKIT_H_
