/*
				Copyright <SWGEmu>
		See file COPYING for copying conditions.*/

#ifndef ARMORTESTKIT_H_
#define ARMORTESTKIT_H_

#include "server/zone/objects/creature/CreatureObject.h"
#include "server/zone/objects/player/PlayerObject.h"
#include "server/zone/objects/draftschematic/DraftSchematic.h"
#include "server/zone/objects/resource/ResourceSpawn.h"
#include "server/zone/objects/resource/ResourceContainer.h"
#include "server/zone/managers/resource/ResourceManager.h"
#include "server/zone/managers/resource/resourcespawner/ResourceSpawner.h"
#include "server/zone/managers/crafting/schematicmap/SchematicMap.h"
#include "server/zone/managers/crafting/CraftingManager.h"
#include "server/zone/objects/manufactureschematic/ManufactureSchematic.h"
#include "server/zone/objects/factorycrate/FactoryCrate.h"

/**
 * Staff test kits for the armor revamp.
 *   /object armortestkit  - resources for the armor pieces + factory crates of max-quality segments and cloth components (no RIS)
 *   /object ristestkit    - RIS piece resources, crates of RIS segments and synthetic cloth, kimogila scales and the RIS schematics
 * Quantities cover three full sets of every family.
 *   /object mandoarmor    - a full set of Mandalorian armor
 */
class ArmorTestKit {
	struct KitResource {
		const char* type;
		int quantity;
	};

	struct KitComponent {
		const char* objectTemplate;
		int quantity;
	};

	struct KitCrate {
		const char* draftSchematic;
		int quantity;
	};

	static int freeInventorySlots(SceneObject* inventory) {
		return (int)inventory->getContainerVolumeLimit() - inventory->getCountableObjectsRecursive();
	}

	static bool checkRoom(CreatureObject* creature, SceneObject* inventory, int needed, const String& kitName) {
		const int freeSlots = freeInventorySlots(inventory);

		if (freeSlots >= needed)
			return true;

		creature->sendSystemMessage(kitName + " needs " + String::valueOf(needed) + " free inventory slots, you have " + String::valueOf(freeSlots) + ".");
		return false;
	}

	// One new max-quality spawn per resource class
	static int giveResources(ResourceManager* resourceManager, CreatureObject* creature, SceneObject* inventory, const KitResource* resources, int count, const String& kitName) {
		const String maxStats = " res_cold_resist,1000 res_conductivity,1000 res_decay_resist,1000 res_flavor,1000 res_heat_resist,1000"
								" res_malleability,1000 res_potential_energy,1000 res_quality,1000 res_shock_resistance,1000 res_toughness,1000";
		int resourcesGiven = 0;

		for (int i = 0; i < count; ++i) {
			const String type = resources[i].type;
			ManagedReference<ResourceSpawn*> spawn;

			{
				Locker managerLocker(resourceManager, creature);
				spawn = resourceManager->getResourceSpawner()->manualCreateResourceSpawn(creature, UnicodeString(type + maxStats));
			}

			if (spawn == nullptr) {
				creature->sendSystemMessage(kitName + ": could not spawn resource class " + type);
				continue;
			}

			Locker spawnLocker(spawn, creature);

			Reference<ResourceContainer*> container = spawn->createResource(resources[i].quantity);

			if (container == nullptr)
				continue;

			Locker containerLocker(container, creature);

			if (inventory->transferObject(container, -1, true)) {
				inventory->broadcastObject(container, true);
				++resourcesGiven;
			} else {
				container->destroyObjectFromDatabase(true);
			}
		}

		return resourcesGiven;
	}

	static int giveItems(ZoneServer* zoneServer, CreatureObject* creature, SceneObject* inventory, const KitComponent* items, int count, const String& kitName) {
		int itemsGiven = 0;

		for (int i = 0; i < count; ++i) {
			const String templatePath = items[i].objectTemplate;
			ManagedReference<TangibleObject*> object = zoneServer->createObject(templatePath.hashCode(), 1).castTo<TangibleObject*>();

			if (object == nullptr) {
				creature->sendSystemMessage(kitName + ": could not create " + templatePath);
				continue;
			}

			Locker objectLocker(object, creature);

			object->createChildObjects();

			if (items[i].quantity > 1)
				object->setUseCount(items[i].quantity);

			if (inventory->transferObject(object, -1, true)) {
				inventory->broadcastObject(object, true);
				++itemsGiven;
			} else {
				object->destroyObjectFromDatabase(true);
			}
		}

		return itemsGiven;
	}

	// Crafts one prototype from the draft schematic with every experimental attribute at 100%
	// (same path as /generateCraftedItem) and packs it into a factory crate of the given size.
	static bool giveCraftedCrate(ZoneServer* zoneServer, CreatureObject* creature, SceneObject* inventory, const KitCrate& entry, const String& kitName) {
		const String path = entry.draftSchematic;
		ManagedReference<CraftingManager*> craftingManager = zoneServer->getCraftingManager();
		ManagedReference<DraftSchematic*> draftSchematic = zoneServer->createObject(path.hashCode(), 0).castTo<DraftSchematic*>();

		if (craftingManager == nullptr || draftSchematic == nullptr || !draftSchematic->isValidDraftSchematic()) {
			creature->sendSystemMessage(kitName + ": invalid draft schematic " + path);
			return false;
		}

		ManagedReference<ManufactureSchematic*> manuSchematic = draftSchematic->createManufactureSchematic().castTo<ManufactureSchematic*>();
		ManagedReference<TangibleObject*> prototype = zoneServer->createObject(draftSchematic->getTanoCRC(), 2).castTo<TangibleObject*>();

		if (manuSchematic == nullptr || prototype == nullptr) {
			creature->sendSystemMessage(kitName + ": could not craft " + path);

			if (prototype != nullptr) {
				Locker locker(prototype);
				prototype->destroyObjectFromDatabase(true);
			}

			return false;
		}

		Locker locker(prototype);

		{
			Locker schematicLocker(manuSchematic, prototype);

			craftingManager->setInitialCraftingValues(prototype, manuSchematic, CraftingManager::GREATSUCCESS);

			Reference<CraftingValues*> craftingValues = manuSchematic->getCraftingValues();
			craftingValues->setManufactureSchematic(manuSchematic);
			craftingValues->setPlayer(creature);

			for (int i = 0; i < craftingValues->getTotalVisibleAttributeGroups(); ++i) {
				const String visibleGroup = craftingValues->getVisibleAttributeGroup(i);

				for (int j = 0; j < craftingValues->getTotalExperimentalAttributes(); ++j) {
					const String attribute = craftingValues->getAttribute(j);

					if (craftingValues->getAttributeGroup(attribute) == visibleGroup)
						craftingValues->setCurrentPercentage(attribute, 1.f, 5.f);
				}
			}

			craftingValues->recalculateValues(true);
			prototype->updateCraftingValues(craftingValues, true);
		}

		prototype->createChildObjects();
		String crafterName = creature->getFirstName();
		prototype->setCraftersName(crafterName);
		prototype->setCraftersID(creature->getObjectID());

		String serial = craftingManager->generateSerial();
		prototype->setSerialNumber(serial);
		prototype->updateToDatabase();

		String crateType = draftSchematic->getFactoryCrateType();
		ManagedReference<FactoryCrate*> crate = prototype->createFactoryCrate(entry.quantity, crateType, true);

		if (crate == nullptr) {
			creature->sendSystemMessage(kitName + ": could not crate " + path);
			prototype->destroyObjectFromDatabase(true);
			return false;
		}

		Locker crateLocker(crate, prototype);

		crate->setUseCount(entry.quantity);

		if (!inventory->transferObject(crate, -1, true)) {
			crate->destroyObjectFromDatabase(true);
			return false;
		}

		crate->sendTo(creature, true);
		return true;
	}

	static int giveCrates(ZoneServer* zoneServer, CreatureObject* creature, SceneObject* inventory, const KitCrate* crates, int count, const String& kitName) {
		int cratesGiven = 0;

		for (int i = 0; i < count; ++i) {
			if (giveCraftedCrate(zoneServer, creature, inventory, crates[i], kitName))
				++cratesGiven;
		}

		return cratesGiven;
	}

public:
	/**
	 * Armorsmith armor (every crafted family except RIS): max-quality resources for the armor pieces themselves,
	 * and factory crates of max-quality segments and cloth components, so nothing below the piece needs crafting.
	 */
	static void give(ZoneServer* zoneServer, CreatureObject* creature) {
		static const KitResource resources[] = {
		{"aluminum", 2000},
		{"bone", 1900},
		{"bone_avian", 300},
		{"bone_mammal_dantooine", 200},
		{"copper", 600},
		{"copper_beyrllius", 1400},
		{"copper_mythra", 400},
		{"fiberplast", 1100},
		{"fiberplast_corellia", 1400},
		{"fiberplast_naboo", 2000},
		{"fuel_petrochem_solid_known", 3100},
		{"hide", 2000},
		{"hide_bristley", 500},
		{"hide_leathery", 3000},
		{"hide_leathery_lok", 3400},
		{"hide_scaley", 3900},
		{"hide_wooly", 4200},
		{"hide_wooly_naboo", 400},
		{"hide_wooly_tatooine", 700},
		{"iron", 900},
		{"metal", 2600},
		{"metal_ferrous", 700},
		{"ore_intrusive", 3100},
		{"petrochem_inert", 400},
		{"petrochem_inert_polymer", 3600},
		{"softwood_evergreen_dathomir", 900},
		{"steel", 900},
		{"steel_neutronium", 400},
		{"wood", 400},
		{"wood_deciduous_endor", 700},
		};

		static const KitCrate crates[] = {
			{"object/draft_schematic/armor/armor_segment.iff", 27},				// tantel
			{"object/draft_schematic/armor/armor_segment_bone.iff", 27},
			{"object/draft_schematic/armor/armor_segment_chitin.iff", 126},			// chitin, ithorian guardian
			{"object/draft_schematic/armor/armor_segment_composite.iff", 126},		// composite, ithorian sentinel
			{"object/draft_schematic/armor/armor_segment_kashyyykian_black_mtn.iff", 30},
			{"object/draft_schematic/armor/armor_segment_kashyyykian_ceremonial.iff", 33},
			{"object/draft_schematic/armor/armor_segment_kashyyykian_hunting.iff", 33},
			{"object/draft_schematic/armor/armor_segment_padded.iff", 99},			// padded, ithorian defender
			{"object/draft_schematic/armor/armor_segment_ubese.iff", 51},
			{"object/draft_schematic/armor/armor_segment_zam.iff", 15},
			{"object/draft_schematic/clothing/component/clothing_fiberplast_panel.iff", 153},
			{"object/draft_schematic/clothing/component/clothing_padding_segment.iff", 99},
			{"object/draft_schematic/clothing/component/clothing_reinforced_fiber_panels.iff", 195},
			{"object/draft_schematic/clothing/component/clothing_synthetic_cloth.iff", 213},
		};

		const int resourceCount = sizeof(resources) / sizeof(resources[0]);
		const int crateCount = sizeof(crates) / sizeof(crates[0]);
		const String kitName = "Armor test kit";

		ManagedReference<SceneObject*> inventory = creature->getSlottedObject("inventory");
		ManagedReference<ResourceManager*> resourceManager = zoneServer->getResourceManager();

		if (inventory == nullptr || resourceManager == nullptr)
			return;

		if (!checkRoom(creature, inventory, resourceCount + crateCount, kitName))
			return;

		const int resourcesGiven = giveResources(resourceManager, creature, inventory, resources, resourceCount, kitName);
		const int cratesGiven = giveCrates(zoneServer, creature, inventory, crates, crateCount, kitName);

		creature->sendSystemMessage(kitName + ": " + String::valueOf(resourcesGiven) + "/" + String::valueOf(resourceCount) + " max-quality resources and "
				+ String::valueOf(cratesGiven) + "/" + String::valueOf(crateCount) + " crates of max-quality segments and cloth components added.");
		creature->info(true) << "/object armortestkit given to " << creature->getFirstName();
	}

	/**
	 * RIS armor: max-quality resources for the pieces, crates of max-quality RIS segments and synthetic cloth,
	 * kimogila scales (loot, so a plain stack) and the RIS loot schematics.
	 */
	static void giveRis(ZoneServer* zoneServer, CreatureObject* creature) {
		static const KitResource resources[] = {
		{"aluminum_chromium", 1700},
		{"armophous_vendusii", 4700},
		{"copper_platinite", 1400},
		{"fiberplast_talus", 2100},
		{"fuel_petrochem_solid_known", 2500},
		{"hide_wooly_rori", 1000},
		};

		static const KitCrate crates[] = {
			{"object/draft_schematic/armor/armor_segment_ris.iff", 27},
			{"object/draft_schematic/clothing/component/clothing_synthetic_cloth.iff", 27},
		};

		static const KitComponent components[] = {
			{"object/tangible/component/armor/scale_giant_dune_kimogila.iff", 27},
		};

		static const char* risSchematics[] = {
			"object/draft_schematic/clothing/clothing_armor_ris_bicep_l.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_bicep_r.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_boots.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_bracer_l.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_bracer_r.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_chest_plate.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_gloves.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_helmet.iff",
			"object/draft_schematic/clothing/clothing_armor_ris_leggings.iff",
		};

		const int resourceCount = sizeof(resources) / sizeof(resources[0]);
		const int crateCount = sizeof(crates) / sizeof(crates[0]);
		const int componentCount = sizeof(components) / sizeof(components[0]);
		const String kitName = "RIS test kit";

		ManagedReference<SceneObject*> inventory = creature->getSlottedObject("inventory");
		Reference<PlayerObject*> ghost = creature->getPlayerObject();
		ManagedReference<ResourceManager*> resourceManager = zoneServer->getResourceManager();

		if (inventory == nullptr || ghost == nullptr || resourceManager == nullptr)
			return;

		if (!checkRoom(creature, inventory, resourceCount + crateCount + componentCount, kitName))
			return;

		const int resourcesGiven = giveResources(resourceManager, creature, inventory, resources, resourceCount, kitName);
		const int cratesGiven = giveCrates(zoneServer, creature, inventory, crates, crateCount, kitName);
		const int componentsGiven = giveItems(zoneServer, creature, inventory, components, componentCount, kitName);

		// RIS schematics are loot/quest rewards, so grant them directly
		for (const char* path : risSchematics) {
			ManagedReference<DraftSchematic*> schematic = SchematicMap::instance()->get(String(path).hashCode());

			if (schematic == nullptr) {
				creature->sendSystemMessage(kitName + ": missing schematic " + String(path));
				continue;
			}

			ghost->addRewardedSchematic(schematic, SchematicList::LOOT, 10, true);
		}

		creature->sendSystemMessage(kitName + ": " + String::valueOf(resourcesGiven) + "/" + String::valueOf(resourceCount) + " max-quality resources, "
				+ String::valueOf(cratesGiven) + "/" + String::valueOf(crateCount) + " crates of max-quality components, "
				+ String::valueOf(componentsGiven) + " kimogila scale stack and RIS piece schematics (10 uses each) added.");
		creature->info(true) << "/object ristestkit given to " << creature->getFirstName();
	}

	/**
	 * A full set of Death Watch Mandalorian armor (stats come from the templates).
	 */
	static void giveMandalorian(ZoneServer* zoneServer, CreatureObject* creature) {
		static const KitComponent pieces[] = {
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_helmet.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_chest_plate.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_leggings.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_bicep_l.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_bicep_r.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_bracer_l.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_bracer_r.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_gloves.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_belt.iff", 1},
			{"object/tangible/wearables/armor/mandalorian/armor_mandalorian_shoes.iff", 1},
		};

		const int pieceCount = sizeof(pieces) / sizeof(pieces[0]);
		const String kitName = "Mandalorian armor";

		ManagedReference<SceneObject*> inventory = creature->getSlottedObject("inventory");

		if (inventory == nullptr)
			return;

		if (!checkRoom(creature, inventory, pieceCount, kitName))
			return;

		const int piecesGiven = giveItems(zoneServer, creature, inventory, pieces, pieceCount, kitName);

		creature->sendSystemMessage(kitName + ": " + String::valueOf(piecesGiven) + "/" + String::valueOf(pieceCount) + " pieces added.");
		creature->info(true) << "/object mandoarmor given to " << creature->getFirstName();
	}
};

#endif // ARMORTESTKIT_H_
