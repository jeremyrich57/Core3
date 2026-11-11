/*
 * SystemVendorManager.h
 *
 * Server-owned NPC vendors that sell configured stock through the normal vendor UI.
 * Vendors, their display stock and their listings are all transient: they are rebuilt
 * from scripts/managers/system_vendor_manager.lua on every server start and never touch
 * the auction or object databases. A purchase hands the buyer a freshly generated,
 * persistent copy of the listed item, so stock never runs out.
 */

#ifndef SYSTEMVENDORMANAGER_H_
#define SYSTEMVENDORMANAGER_H_

#include "engine/engine.h"
#include "engine/lua/LuaObject.h"
#include "server/zone/objects/creature/CreatureObject.h"
#include "server/zone/objects/auction/AuctionItem.h"
#include "server/zone/objects/tangible/TangibleObject.h"
#include "server/zone/objects/transaction/TransactionLog.h"

namespace server {
namespace zone {
	class ZoneServer;
}
}

using namespace server::zone;

namespace server {
namespace zone {
namespace managers {
namespace vendor {

class SystemVendorStockEntry : public Object {
public:
	// Exactly one of these is set: a loot item template name (base-quality loot stats)
	// or a plain object template path (template defaults, e.g. tools and backpacks)
	String lootTemplate;
	String objectTemplate;

	int price = 0;

	// Per-item weapon multipliers, applied on top of the vendor's weaponAdjust
	float weaponSpeedMultiplier = 1.f;
	float weaponDamageMultiplier = 1.f;

	// Armor: added to every resist above 0, then specific resists set to a flat value
	float armorBonus = 0.f;
	VectorMap<int, float> armorResists;

	// Transient object shown in the vendor list, and its listing
	ManagedReference<TangibleObject*> displayObject;
	ManagedReference<AuctionItem*> auctionItem;

	String getSourceName() const {
		return lootTemplate.isEmpty() ? objectTemplate : lootTemplate;
	}
};

class SystemVendor : public Object {
public:
	String key;
	ManagedReference<CreatureObject*> vendor;

	// Applied to every weapon this vendor sells: attack time and min/max damage are
	// multiplied by these after the base-quality stats are set
	float weaponSpeedMultiplier = 1.f;
	float weaponDamageMultiplier = 1.f;

	// Keyed by the listed display object's ID, which is what the client buys by
	VectorMap<uint64, Reference<SystemVendorStockEntry*> > listings;

	// Transient stall decoration (furniture, banners, items) spawned around the vendor
	Vector<ManagedReference<SceneObject*> > props;
};

class SystemVendorManager : public Singleton<SystemVendorManager>, public Logger, public Object {
	ManagedReference<ZoneServer*> zoneServer;

	Mutex mutex;

	VectorMap<uint64, Reference<SystemVendor*> > vendors;

public:
	SystemVendorManager();

	// Called once from ZoneServer after the AuctionManager has initialized
	void initialize(ZoneServer* server);

	static bool isSystemVendor(SceneObject* vendor);

	// Player is locked. Returns a BidAuctionResponseMessage result code.
	int purchaseItem(CreatureObject* player, SceneObject* vendor, AuctionItem* item);

private:
	void spawnVendor(LuaObject& vendorConfig);

	// Spawns the vendor's props, positioned relative to the vendor's position and heading
	void spawnProps(SystemVendor* systemVendor, LuaObject& vendorConfig, Zone* zone, const Vector3& origin, float heading, uint64 cellID);

	void dressVendor(CreatureObject* vendor, const String& outfitName);

	bool addListing(SystemVendor* systemVendor, Reference<SystemVendorStockEntry*> entry);

	// Creates an item for the entry: transient (persistenceLevel 0) for display,
	// persistent for a purchase
	Reference<TangibleObject*> createStockObject(TransactionLog& trx, const SystemVendor* systemVendor, const SystemVendorStockEntry* entry, int persistenceLevel);

	void applyWeaponAdjustments(const SystemVendor* systemVendor, const SystemVendorStockEntry* entry, TangibleObject* object);

	void applyArmorAdjustments(const SystemVendorStockEntry* entry, TangibleObject* object);

	static int getNameSpecies(const String& species);
};

}
}
}
}

using namespace server::zone::managers::vendor;

#endif /* SYSTEMVENDORMANAGER_H_ */
