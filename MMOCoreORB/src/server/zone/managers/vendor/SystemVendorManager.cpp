/*
 * SystemVendorManager.cpp
 */

#include "SystemVendorManager.h"
#include "VendorOutfitManager.h"
#include "server/zone/ZoneServer.h"
#include "server/zone/Zone.h"
#include "server/zone/managers/auction/AuctionManager.h"
#include "server/zone/managers/auction/AuctionsMap.h"
#include "server/zone/managers/loot/LootManager.h"
#include "server/zone/managers/loot/LootGroupMap.h"
#include "server/zone/managers/name/NameManager.h"
#include "server/zone/objects/tangible/components/vendor/VendorDataComponent.h"
#include "server/zone/objects/tangible/weapon/WeaponObject.h"
#include "server/zone/objects/tangible/wearables/ArmorObject.h"
#include "templates/tangible/SharedWeaponObjectTemplate.h"

namespace {
	struct ArmorResistType {
		const char* name;
		int type;
	};

	const ArmorResistType armorResistTypes[] = {
		{ "kinetic", SharedWeaponObjectTemplate::KINETIC },
		{ "energy", SharedWeaponObjectTemplate::ENERGY },
		{ "blast", SharedWeaponObjectTemplate::BLAST },
		{ "stun", SharedWeaponObjectTemplate::STUN },
		{ "heat", SharedWeaponObjectTemplate::HEAT },
		{ "cold", SharedWeaponObjectTemplate::COLD },
		{ "acid", SharedWeaponObjectTemplate::ACID },
		{ "electricity", SharedWeaponObjectTemplate::ELECTRICITY },
		{ "lightsaber", SharedWeaponObjectTemplate::LIGHTSABER },
	};

	float getArmorResist(ArmorObject* armor, int type) {
		switch (type) {
		case SharedWeaponObjectTemplate::KINETIC: return armor->getKinetic();
		case SharedWeaponObjectTemplate::ENERGY: return armor->getEnergy();
		case SharedWeaponObjectTemplate::BLAST: return armor->getBlast();
		case SharedWeaponObjectTemplate::STUN: return armor->getStun();
		case SharedWeaponObjectTemplate::HEAT: return armor->getHeat();
		case SharedWeaponObjectTemplate::COLD: return armor->getCold();
		case SharedWeaponObjectTemplate::ACID: return armor->getAcid();
		case SharedWeaponObjectTemplate::ELECTRICITY: return armor->getElectricity();
		case SharedWeaponObjectTemplate::LIGHTSABER: return armor->getLightSaber();
		default: return 0.f;
		}
	}

	void setArmorRawResist(ArmorObject* armor, int type, float value) {
		switch (type) {
		case SharedWeaponObjectTemplate::KINETIC: armor->setKinetic(value); break;
		case SharedWeaponObjectTemplate::ENERGY: armor->setEnergy(value); break;
		case SharedWeaponObjectTemplate::BLAST: armor->setBlast(value); break;
		case SharedWeaponObjectTemplate::STUN: armor->setStun(value); break;
		case SharedWeaponObjectTemplate::HEAT: armor->setHeat(value); break;
		case SharedWeaponObjectTemplate::COLD: armor->setCold(value); break;
		case SharedWeaponObjectTemplate::ACID: armor->setAcid(value); break;
		case SharedWeaponObjectTemplate::ELECTRICITY: armor->setElectricity(value); break;
		case SharedWeaponObjectTemplate::LIGHTSABER: armor->setLightSaber(value); break;
		default: break;
		}
	}

	// The displayed resist is the raw per-type value plus an offset that depends on whether the
	// type is vulnerable (none), special or base protection. Zeroing the raw value reveals the
	// offset, so the raw value can be set to land the final resist exactly on the target.
	void setArmorFinalResist(ArmorObject* armor, int type, float target) {
		setArmorRawResist(armor, type, 0.f);
		float offset = getArmorResist(armor, type);
		setArmorRawResist(armor, type, target - offset);
	}
}
#include "server/zone/objects/transaction/TransactionLog.h"
#include "server/zone/packets/auction/BidAuctionResponseMessage.h"
#include "server/zone/packets/auction/ItemSoldMessage.h"
#include "templates/LootItemTemplate.h"

SystemVendorManager::SystemVendorManager() : Logger("SystemVendorManager") {
}

void SystemVendorManager::initialize(ZoneServer* server) {
	zoneServer = server;

	Lua lua;
	lua.init();

	if (!lua.runFile("scripts/managers/system_vendor_manager.lua")) {
		error() << "Unable to load scripts/managers/system_vendor_manager.lua";
		return;
	}

	LuaObject vendorsTable = lua.getGlobalObject("systemVendors");

	if (!vendorsTable.isValidTable()) {
		info(true) << "No systemVendors table defined, no system vendors spawned.";
		vendorsTable.pop();
		return;
	}

	for (int i = 1; i <= vendorsTable.getTableSize(); ++i) {
		lua_State* L = vendorsTable.getLuaState();
		lua_rawgeti(L, -1, i);
		LuaObject vendorConfig(L);

		if (vendorConfig.isValidTable()) {
			spawnVendor(vendorConfig);
		}

		vendorConfig.pop();
	}

	vendorsTable.pop();

	Locker guard(&mutex);
	info(true) << "Spawned " << vendors.size() << " system vendor(s).";
}

bool SystemVendorManager::isSystemVendor(SceneObject* vendor) {
	if (vendor == nullptr || !vendor->isVendor()) {
		return false;
	}

	DataObjectComponentReference* data = vendor->getDataObjectComponent();

	if (data == nullptr || data->get() == nullptr || !data->get()->isVendorData()) {
		return false;
	}

	VendorDataComponent* vendorData = cast<VendorDataComponent*>(data->get());

	return vendorData != nullptr && vendorData->isSystemVendor();
}

void SystemVendorManager::spawnVendor(LuaObject& vendorConfig) {
	const String key = vendorConfig.getStringField("key");
	const String planet = vendorConfig.getStringField("planet");
	const String templatePath = vendorConfig.getStringField("template");

	Zone* zone = zoneServer->getZone(planet);

	if (zone == nullptr) {
		info(true) << "Skipping system vendor " << key << ", zone " << planet << " is not enabled.";
		return;
	}

	ManagedReference<AuctionManager*> auctionManager = zoneServer->getAuctionManager();

	if (auctionManager == nullptr || auctionManager->getAuctionMap() == nullptr) {
		error() << "Skipping system vendor " << key << ", AuctionManager is not initialized.";
		return;
	}

	ManagedReference<CreatureObject*> vendor = zoneServer->createObject(templatePath.hashCode(), 0).castTo<CreatureObject*>();

	if (vendor == nullptr || !vendor->isVendor()) {
		error() << "System vendor " << key << ": template is not a vendor creature: " << templatePath;
		return;
	}

	Locker locker(vendor);

	DataObjectComponentReference* data = vendor->getDataObjectComponent();

	if (data == nullptr || data->get() == nullptr || !data->get()->isVendorData()) {
		error() << "System vendor " << key << ": template has no vendor data component: " << templatePath;
		return;
	}

	VendorDataComponent* vendorData = cast<VendorDataComponent*>(data->get());

	vendorData->setSystemVendor(true);
	vendorData->setOwnerId(0);

	String name = vendorConfig.getStringField("name");

	if (name.isEmpty()) {
		NameManager* nameManager = zoneServer->getNameManager();
		String species = vendorConfig.getStringField("nameSpecies", "human");

		if (nameManager != nullptr) {
			name = nameManager->makeCreatureName(NameManagerType::GENERIC, getNameSpecies(species));
		}

		if (name.isEmpty()) {
			name = "Quartermaster";
		}
	}

	const String title = vendorConfig.getStringField("title");
	const String displayName = title.isEmpty() ? name : name + " (" + title + ")";

	vendor->setCustomObjectName(displayName, false);
	vendor->setMaxCondition(1000, false);
	vendor->setConditionDamage(0, false);

	vendor->createChildObjects();

	dressVendor(vendor, vendorConfig.getStringField("outfit"));

	const float x = vendorConfig.getFloatField("x");
	const float y = vendorConfig.getFloatField("y");
	const uint64 cellID = vendorConfig.getLongField("cellId");

	// z is optional outdoors, the vendor is placed on the terrain when it is left out
	const float noHeight = -100000.f;
	float z = vendorConfig.getFloatField("z", noHeight);

	if (z == noHeight) {
		z = cellID == 0 ? zone->getHeight(x, y) : 0.f;
	}

	vendor->initializePosition(x, z, y);
	vendor->setDirection(Math::deg2rad(vendorConfig.getFloatField("heading")));

	if (cellID != 0) {
		ManagedReference<SceneObject*> cell = zoneServer->getObject(cellID);

		if (cell == nullptr || !cell->isCellObject()) {
			error() << "System vendor " << key << ": invalid cellId " << cellID;
			return;
		}

		cell->transferObject(vendor, -1, true);
	} else {
		zone->transferObject(vendor, -1, true);
	}

	// Computes the vendor UID from its zone, region, name and position, then keeps it out
	// of galaxy and planet vendor searches
	vendorData->setInitialized(true);
	vendorData->setVendorSearchEnabled(false);

	Reference<SystemVendor*> systemVendor = new SystemVendor();
	systemVendor->key = key;
	systemVendor->vendor = vendor;

	LuaObject weaponAdjust = vendorConfig.getObjectField("weaponAdjust");

	if (weaponAdjust.isValidTable()) {
		systemVendor->weaponSpeedMultiplier = Math::max(0.1f, weaponAdjust.getFloatField("speed", 1.f));
		systemVendor->weaponDamageMultiplier = Math::max(0.1f, weaponAdjust.getFloatField("damage", 1.f));
	}

	weaponAdjust.pop();

	LuaObject stock = vendorConfig.getObjectField("stock");

	if (stock.isValidTable()) {
		for (int i = 1; i <= stock.getTableSize(); ++i) {
			lua_State* L = stock.getLuaState();
			lua_rawgeti(L, -1, i);
			LuaObject stockConfig(L);

			Reference<SystemVendorStockEntry*> entry = new SystemVendorStockEntry();
			entry->lootTemplate = stockConfig.getStringField("loot");
			entry->objectTemplate = stockConfig.getStringField("template");
			entry->price = stockConfig.getIntField("price");
			entry->weaponSpeedMultiplier = Math::max(0.1f, stockConfig.getFloatField("speed", 1.f));
			entry->weaponDamageMultiplier = Math::max(0.1f, stockConfig.getFloatField("damage", 1.f));
			entry->armorBonus = stockConfig.getFloatField("armorBonus", 0.f);

			LuaObject resists = stockConfig.getObjectField("resists");

			if (resists.isValidTable()) {
				for (const auto& resistType : armorResistTypes) {
					float value = resists.getFloatField(resistType.name, -1.f);

					if (value >= 0.f) {
						entry->armorResists.put(resistType.type, Math::min(value, 80.f));
					}
				}
			}

			resists.pop();

			stockConfig.pop();

			if (entry->lootTemplate.isEmpty() == entry->objectTemplate.isEmpty()) {
				error() << "System vendor " << key << ": stock entry " << i << " needs exactly one of loot or template.";
				continue;
			}

			if (entry->price < 1 || entry->price > AuctionManager::MAXVENDORPRICE) {
				error() << "System vendor " << key << ": stock entry " << entry->getSourceName() << " has invalid price " << entry->price;
				continue;
			}

			addListing(systemVendor, entry);
		}
	}

	stock.pop();

	locker.release();

	spawnProps(systemVendor, vendorConfig, zone, Vector3(x, y, z), vendorConfig.getFloatField("heading"), cellID);

	Locker guard(&mutex);
	vendors.put(vendor->getObjectID(), systemVendor);

	info(true) << "Spawned system vendor " << key << " \"" << displayName << "\" on " << planet
		<< " at " << x << ", " << z << ", " << y << " with " << systemVendor->listings.size() << " listing(s) and "
		<< systemVendor->props.size() << " prop(s).";
}

void SystemVendorManager::spawnProps(SystemVendor* systemVendor, LuaObject& vendorConfig, Zone* zone, const Vector3& origin, float heading, uint64 cellID) {
	LuaObject props = vendorConfig.getObjectField("props");

	if (!props.isValidTable()) {
		props.pop();
		return;
	}

	ManagedReference<SceneObject*> cell = nullptr;

	if (cellID != 0) {
		cell = zoneServer->getObject(cellID);

		if (cell == nullptr || !cell->isCellObject()) {
			props.pop();
			return;
		}
	}

	// Offsets are in the vendor's frame: x to the vendor's right, y in front of him
	const float headingRad = Math::deg2rad(heading);
	const float sinH = Math::sin(headingRad);
	const float cosH = Math::cos(headingRad);

	for (int i = 1; i <= props.getTableSize(); ++i) {
		lua_State* L = props.getLuaState();
		lua_rawgeti(L, -1, i);
		LuaObject propConfig(L);

		const String templatePath = propConfig.getStringField("template");
		const float right = propConfig.getFloatField("x");
		const float forward = propConfig.getFloatField("y");
		const float height = propConfig.getFloatField("z");
		const float propHeading = propConfig.getFloatField("heading");
		const String name = propConfig.getStringField("name");

		propConfig.pop();

		ManagedReference<SceneObject*> prop = zoneServer->createObject(templatePath.hashCode(), 0);

		if (prop == nullptr) {
			error() << "System vendor " << systemVendor->key << ": unable to create prop " << templatePath;
			continue;
		}

		Locker locker(prop);

		const float px = origin.getX() + right * cosH + forward * sinH;
		const float py = origin.getY() - right * sinH + forward * cosH;
		const float ground = cell == nullptr ? zone->getHeight(px, py) : origin.getZ();

		prop->initializePosition(px, ground + height, py);
		prop->setDirection(Math::deg2rad(heading + propHeading));

		// Props sit in the world (or a cell) with no owner, so they can't be picked up or moved
		ContainerPermissions* permissions = prop->getContainerPermissionsForUpdate();
		permissions->setInheritPermissionsFromParent(false);
		permissions->setDefaultDenyPermission(ContainerPermissions::MOVECONTAINER);
		permissions->setDenyPermission("admin", ContainerPermissions::MOVECONTAINER);

		if (!name.isEmpty()) {
			prop->setCustomObjectName(name, false);
		}

		if (cell != nullptr) {
			cell->transferObject(prop, -1, true);
		} else {
			zone->transferObject(prop, -1, true);
		}

		systemVendor->props.add(prop);
	}

	props.pop();
}

void SystemVendorManager::dressVendor(CreatureObject* vendor, const String& outfitName) {
	if (outfitName.isEmpty()) {
		return;
	}

	Reference<Outfit*> outfit = VendorOutfitManager::instance()->getOutfit(outfitName);

	if (outfit == nullptr) {
		error() << "Unknown vendor outfit: " << outfitName;
		return;
	}

	Vector<uint32>* clothing = outfit->getClothing();

	for (int i = 0; i < clothing->size(); ++i) {
		ManagedReference<SceneObject*> obj = zoneServer->createObject(clothing->get(i), 0);

		if (obj == nullptr) {
			continue;
		}

		for (int j = 0; j < obj->getArrangementDescriptorSize(); ++j) {
			const Vector<String>* descriptors = obj->getArrangementDescriptor(j);

			for (int k = 0; k < descriptors->size(); ++k) {
				ManagedReference<SceneObject*> slot = vendor->getSlottedObject(descriptors->get(k));

				if (slot != nullptr) {
					slot->destroyObjectFromWorld(true);
					slot->destroyObjectFromDatabase(true);
				}
			}
		}

		String errorDescription;
		int errorCode = vendor->canAddObject(obj, 4, errorDescription);

		if (errorCode != 0 || !vendor->transferObject(obj, 4)) {
			error() << "Outfit " << outfitName << ": unable to put " << obj->getObjectTemplate()->getFullTemplateString()
				<< " on " << vendor->getObjectTemplate()->getFullTemplateString() << " (error " << errorCode << " " << errorDescription << ")";
			obj->destroyObjectFromDatabase(true);
		}
	}
}

bool SystemVendorManager::addListing(SystemVendor* systemVendor, Reference<SystemVendorStockEntry*> entry) {
	ManagedReference<CreatureObject*> vendor = systemVendor->vendor;
	ManagedReference<AuctionManager*> auctionManager = zoneServer->getAuctionManager();
	ManagedReference<AuctionsMap*> auctionMap = auctionManager->getAuctionMap();

	// Display objects are transient and never handed to a player, nothing worth logging
	TransactionLog trx(TrxCode::LUASCRIPT, vendor);
	trx.discard();

	Reference<TangibleObject*> displayObject = createStockObject(trx, systemVendor, entry, 0);

	if (displayObject == nullptr) {
		error() << "System vendor " << systemVendor->key << ": failed to create stock item " << entry->getSourceName();
		return false;
	}

	Locker olocker(displayObject, vendor);

	ManagedReference<AuctionItem*> item = new AuctionItem(displayObject->getObjectID());

	// Vendor listings are sorted by the listing's own object ID, so it needs a unique one.
	// deploy() assigns a free transient ID, the listing is still never saved.
	item->deploy();

	Locker ilocker(item);

	item->setSystemVendorItem(true);
	item->setVendorUID(auctionManager->getVendorUID(vendor));
	item->setOnBazaar(false);
	item->setVendorID(vendor->getObjectID());
	item->setItemName(displayObject->getDisplayedName());
	item->setItemDescription("");
	item->setItemType(displayObject->getClientGameObjectType());
	item->setPrice(entry->price);
	item->setAuction(false);
	item->setStatus(AuctionItem::FORSALE);
	item->setBuyerID(0);
	item->setBidderName("");
	item->setSize(displayObject->getSizeOnVendorRecursive());
	item->setExpireTime(time(0) + AuctionManager::VENDOREXPIREPERIOD);
	item->setOwnerID(0);
	item->setOwnerName(vendor->getDisplayedName());

	int result = auctionMap->addItem(nullptr, vendor, item);

	if (result != ItemSoldMessage::SUCCESS) {
		error() << "System vendor " << systemVendor->key << ": failed to list " << entry->getSourceName() << ", result " << ItemSoldMessage::statusToString(result);
		return false;
	}

	entry->displayObject = displayObject;
	entry->auctionItem = item;

	systemVendor->listings.put(displayObject->getObjectID(), entry);

	return true;
}

Reference<TangibleObject*> SystemVendorManager::createStockObject(TransactionLog& trx, const SystemVendor* systemVendor, const SystemVendorStockEntry* entry, int persistenceLevel) {
	if (!entry->lootTemplate.isEmpty()) {
		ManagedReference<LootManager*> lootManager = zoneServer->getLootManager();

		if (lootManager == nullptr) {
			return nullptr;
		}

		const LootItemTemplate* lootTemplate = lootManager->getLootMap()->getLootItemTemplate(entry->lootTemplate);

		if (lootTemplate == nullptr) {
			error() << "Unknown loot item template: " << entry->lootTemplate;
			return nullptr;
		}

		Reference<TangibleObject*> object = lootManager->createBaseLootObject(trx, lootTemplate, persistenceLevel);

		if (object != nullptr) {
			Locker locker(object);
			applyWeaponAdjustments(systemVendor, entry, object);
			applyArmorAdjustments(entry, object);
		}

		return object;
	}

	Reference<TangibleObject*> object = zoneServer->createObject(entry->objectTemplate.hashCode(), persistenceLevel).castTo<TangibleObject*>();

	if (object == nullptr) {
		error() << "Unable to create stock object from template: " << entry->objectTemplate;
		return nullptr;
	}

	Locker locker(object);

	object->createChildObjects();
	object->setJunkDealerNeeded(0);
	object->setJunkValue(0);

	applyWeaponAdjustments(systemVendor, entry, object);
	applyArmorAdjustments(entry, object);

	trx.addState("systemVendorTemplate", entry->objectTemplate);

	return object;
}

void SystemVendorManager::applyArmorAdjustments(const SystemVendorStockEntry* entry, TangibleObject* object) {
	if (!object->isArmorObject() || (entry->armorBonus == 0.f && entry->armorResists.size() == 0)) {
		return;
	}

	ArmorObject* armor = cast<ArmorObject*>(object);

	if (armor == nullptr) {
		return;
	}

	if (entry->armorBonus != 0.f) {
		for (const auto& resistType : armorResistTypes) {
			float current = getArmorResist(armor, resistType.type);

			if (current > 0.f) {
				setArmorFinalResist(armor, resistType.type, Math::min(current + entry->armorBonus, 80.f));
			}
		}
	}

	for (int i = 0; i < entry->armorResists.size(); ++i) {
		setArmorFinalResist(armor, entry->armorResists.elementAt(i).getKey(), entry->armorResists.elementAt(i).getValue());
	}
}

void SystemVendorManager::applyWeaponAdjustments(const SystemVendor* systemVendor, const SystemVendorStockEntry* entry, TangibleObject* object) {
	if (!object->isWeaponObject()) {
		return;
	}

	WeaponObject* weapon = cast<WeaponObject*>(object);

	if (weapon == nullptr) {
		return;
	}

	const float speedMultiplier = systemVendor->weaponSpeedMultiplier * entry->weaponSpeedMultiplier;
	const float damageMultiplier = systemVendor->weaponDamageMultiplier * entry->weaponDamageMultiplier;

	if (speedMultiplier != 1.f) {
		// Attack speed is shown with one decimal place
		float speed = Math::max(1.f, weapon->getAttackSpeed(false) * speedMultiplier);
		weapon->setAttackSpeed(roundf(speed * 10.f) / 10.f);
	}

	if (damageMultiplier != 1.f) {
		weapon->setMinDamage(roundf(weapon->getMinDamage(false) * damageMultiplier));
		weapon->setMaxDamage(roundf(weapon->getMaxDamage(false) * damageMultiplier));
	}
}

int SystemVendorManager::purchaseItem(CreatureObject* player, SceneObject* vendor, AuctionItem* item) {
	Reference<SystemVendorStockEntry*> entry = nullptr;
	Reference<SystemVendor*> systemVendor = nullptr;

	{
		Locker guard(&mutex);

		systemVendor = vendors.get(vendor->getObjectID());

		if (systemVendor == nullptr) {
			return BidAuctionResponseMessage::INVALIDAUCTIONER;
		}

		entry = systemVendor->listings.get(item->getAuctionedItemObjectID());
	}

	if (entry == nullptr) {
		return BidAuctionResponseMessage::INVALIDITEM;
	}

	Zone* zone = player->getZone();

	if (zone == nullptr || zone != vendor->getZone() || player->getWorldPosition().distanceTo(vendor->getWorldPosition()) > 64.f) {
		return BidAuctionResponseMessage::PURCHASEFAILED;
	}

	const int price = entry->price;

	if (player->getBankCredits() < price) {
		return BidAuctionResponseMessage::NOTENOUGHCREDITS;
	}

	ManagedReference<SceneObject*> inventory = player->getInventory();

	if (inventory == nullptr) {
		return BidAuctionResponseMessage::PURCHASEFAILED;
	}

	if (inventory->isContainerFullRecursive()) {
		player->sendSystemMessage("@error_message:inv_full"); // Your inventory is full.
		return BidAuctionResponseMessage::PURCHASEFAILED;
	}

	TransactionLog trx(player, vendor, TrxCode::INSTANTBUY, price, false);
	trx.addState("systemVendor", vendor->getDisplayedName());
	trx.addState("systemVendorStock", entry->getSourceName());

	Reference<TangibleObject*> product = createStockObject(trx, systemVendor, entry, 2);

	if (product == nullptr) {
		trx.abort() << "Failed to create " << entry->getSourceName();
		return BidAuctionResponseMessage::PURCHASEFAILED;
	}

	Locker clocker(product, player);

	if (!inventory->transferObject(product, -1, false)) {
		trx.abort() << "transferObject failed";
		product->destroyObjectFromDatabase(true);
		return BidAuctionResponseMessage::PURCHASEFAILED;
	}

	inventory->broadcastObject(product, true);

	player->subtractBankCredits(price);

	trx.addRelatedObject(product, true);
	trx.setExportRelatedObjects(true);

	player->sendSystemMessage("You purchase " + product->getDisplayedName() + " for " + String::valueOf(price) + " credits. It has been placed in your inventory.");

	return BidAuctionResponseMessage::SUCCEDED;
}

int SystemVendorManager::getNameSpecies(const String& species) {
	const String lower = species.toLowerCase();

	if (lower == "rodian") return CreatureObject::RODIAN;
	if (lower == "trandoshan") return CreatureObject::TRANDOSHAN;
	if (lower == "moncal") return CreatureObject::MONCAL;
	if (lower == "wookiee") return CreatureObject::WOOKIEE;
	if (lower == "bothan") return CreatureObject::BOTHAN;
	if (lower == "twilek") return CreatureObject::TWILEK;
	if (lower == "zabrak") return CreatureObject::ZABRAK;
	if (lower == "ithorian") return CreatureObject::ITHORIAN;
	if (lower == "sullustan") return CreatureObject::SULLUSTAN;

	return CreatureObject::HUMAN;
}
