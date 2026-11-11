-- System vendors: server-owned NPC vendors that use the normal vendor buy screen.
--
-- Spawned by SystemVendorManager on server start (after the AuctionManager), nothing here
-- is saved to the database. Stock never runs out: every purchase generates a fresh copy
-- of the listed item into the buyer's inventory. Items bought here have no junk dealer
-- value, so they can't be resold to NPCs.
--
-- Vendor fields:
--   key         unique id, used in logs
--   planet      zone name, the vendor is skipped if the zone is not enabled
--   template    a vendor creature template (object/mobile/vendor/*.iff)
--   x, y        world coordinates (or cell coordinates when cellId is set)
--   z           optional outdoors, defaults to the terrain height
--   heading     degrees, 0 = north
--   cellId      optional, cell object id when placing the vendor inside a building
--   outfit      outfit name from scripts/mobile/wearables/*_outfits.lua
--   name        fixed name, leave empty to roll a random one each server start
--   nameSpecies species used for the random name (human, ithorian, rodian, ...)
--   title       shown after the name in parentheses
--
-- The vendors are the Voss brothers of the Voss Syndicate: each gets his own first name
-- and the Voss surname (Thalor in Theed).
--   weaponAdjust optional multipliers applied to every weapon sold, after base stats:
--                 speed  = attack time multiplier (0.6 = 40% faster)
--                 damage = min/max damage multiplier (1.15 = 15% more)
--   stock       list of items, each with a price and exactly one of:
--                 loot     = loot item template name (scripts/loot/items), every stat
--                            at the bottom of its loot range, no bonuses
--                 template = object template path, created with template defaults
--               weapons can also set speed / damage, multiplied on top of weaponAdjust
--               armor can set armorBonus (added to every resist above 0) and/or
--               resists = { kinetic = 25, ... } to set those resists to a flat value
--               (kinetic, energy, blast, stun, heat, cold, acid, electricity, lightsaber; max 80)
--   props       optional stall decoration, spawned with the vendor (transient, can't be picked up):
--                 template = object template path (furniture, static objects or items)
--                 x, y     offset in meters from the vendor: x to his right, y in front of him
--                 z        height above the ground at that spot (e.g. a counter top), default 0
--                 heading  degrees, relative to the vendor's heading, default 0
--                 name     optional custom name
--   greeting    optional: the vendor turns to face a player who walks up, says one of the
--               messages and plays an animation, then turns back. Each player is greeted once,
--               and again only after walking at least 10m past the range.
--                 messages  = list of lines, one picked at random; {name} = player's first name
--                 mood      = chat mood (cheerful, happy, friendly, ...), optional
--                 animation = e.g. wave_greeting, wave_hail, bow, salute1, optional
--                 range     = meters, default 12

-- Padded armor: +25 to every resist via armorBonus, then these set to a flat value
local paddedResists = { kinetic = 45, blast = 52 }

-- Bone armor: flat resists, these replace whatever the loot values give
local boneResists = { kinetic = 25, energy = 52, electricity = 44, heat = 33, acid = 33 }

-- Theed stall (upscale): rug, a long counter with goods on top, elegant furniture and a Naboo
-- banner behind the vendor and lamps either side.
-- Counter top is 1.16m; items are raised so their models rest on it.
local theedStallProps = {
	{ template = "object/tangible/furniture/modern/rug_rect_lg_s02.iff", x = 0, y = 0.6, z = -0.065, heading = 90 },
	{ template = "object/tangible/furniture/modern/bar_piece_straight_s2.iff", x = 0, y = 1.3 },

	-- On the counter
	{ template = "object/weapon/ranged/pistol/pistol_dl44.iff", x = -1.6, y = 1.3, z = 1.23, heading = 90 },
	{ template = "object/weapon/ranged/carbine/carbine_e11.iff", x = -0.8, y = 1.3, z = 1.22, heading = 90 },
	{ template = "object/tangible/dungeon/computer_desktop.iff", x = -0.1, y = 1.3, z = 1.16, heading = 180 }, -- screen toward the vendor
	{ template = "object/weapon/melee/knife/knife_vibroblade.iff", x = 0.6, y = 1.3, z = 1.23, heading = 90 },
	{ template = "object/tangible/crafting/station/generic_tool.iff", x = 1.2, y = 1.3, z = 1.16 },
	{ template = "object/tangible/survey_tool/survey_tool_mineral.iff", x = 1.7, y = 1.3, z = 1.16 },

	-- Behind the vendor
	{ template = "object/tangible/furniture/elegant/armoire_elegant_s01.iff", x = -1.8, y = -1.4 },
	{ template = "object/tangible/furniture/elegant/cabinet_s01.iff", x = 1.8, y = -1.4 },
	{ template = "object/static/structure/naboo/nboo_imprv_bannerpole_s01.iff", x = 0, y = -2.4 },
	{ template = "object/tangible/furniture/all/frn_all_lamp_free_s02_lit.iff", x = -3.0, y = -1.2 },
	{ template = "object/tangible/furniture/all/frn_all_lamp_free_s02_lit.iff", x = 3.0, y = -1.2 },
}

systemVendors = {
	{
		key = "theed_merchant",
		planet = "naboo",
		template = "object/mobile/vendor/ithorian_male.iff",
		x = -4849,
		y = 4091,
		heading = 0,
		outfit = "VossMerchant",
		name = "Thalor Voss",
		nameSpecies = "ithorian",
		title = "Merchant, Voss Syndicate",
		weaponAdjust = { speed = 0.6, damage = 1.15 },
		props = theedStallProps,
		greeting = {
			messages = {
				"Welcome, {name}! The Voss Syndicate's finest goods, at honest prices.",
				"Ah, {name}! Come, come, have a look. Everything here is fresh stock.",
				"Greetings, traveller. Need armor? A good blaster? Thalor has you covered.",
				"Well met, {name}. Browse as long as you like, friend.",
			},
			mood = "cheerful",
			animation = "wave_greeting",
			range = 12,
		},

		stock = {
			-- Padded armor
			{ loot = "padded_armor_chest_plate", price = 4000, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_leggings", price = 3000, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_helmet", price = 2500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_boots", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_gloves", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_bicep_l", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_bicep_r", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_bracer_l", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_bracer_r", price = 1500, armorBonus = 25, resists = paddedResists },
			{ loot = "padded_armor_belt", price = 1000 },

			-- Bone armor
			{ loot = "bone_armor_chest_plate", price = 3500, resists = boneResists },
			{ loot = "bone_armor_leggings", price = 2500, resists = boneResists },
			{ loot = "bone_armor_helmet", price = 2000, resists = boneResists },
			{ loot = "bone_armor_boots", price = 1250, resists = boneResists },
			{ loot = "bone_armor_gloves", price = 1250, resists = boneResists },
			{ loot = "bone_armor_bicep_l", price = 1250, resists = boneResists },
			{ loot = "bone_armor_bicep_r", price = 1250, resists = boneResists },
			{ loot = "bone_armor_bracer_l", price = 1250, resists = boneResists },
			{ loot = "bone_armor_bracer_r", price = 1250, resists = boneResists },

			-- Weapons
			{ loot = "pistol_d18", price = 2000 },
			{ loot = "pistol_dl44", price = 2000 },
			{ loot = "pistol_dh17", price = 2000 },
			{ loot = "carbine_dh17", price = 2000, speed = 1.44 },
			{ loot = "carbine_e11", price = 4500, speed = 1.2, damage = 1.25 },
			{ loot = "rifle_dlt20", price = 2000, damage = 0.9 },
			{ loot = "rifle_e11", price = 5000, damage = 1.5 },
			{ loot = "knife_survival", price = 1000 },
			{ loot = "knife_vibroblade", price = 3500 },
			{ loot = "one_handed_sword", price = 2000 },
			{ loot = "two_handed_sword_cleaver", price = 4500 },
			{ loot = "two_handed_sword_battleaxe", price = 4000 },
			{ loot = "polearm_staff_wood", price = 1500 },
			{ loot = "polearm_lance", price = 3000 },
			{ loot = "polearm_lance_vibrolance", price = 6000 },
			{ loot = "melee_vibroknuckler", price = 5000, damage = 1.25 },

			-- Crafting tools
			{ template = "object/tangible/crafting/station/generic_tool.iff", price = 1000 },
			{ template = "object/tangible/crafting/station/weapon_tool.iff", price = 1500 },
			{ template = "object/tangible/crafting/station/clothing_tool.iff", price = 1500 },
			{ template = "object/tangible/crafting/station/food_tool.iff", price = 1500 },
			{ template = "object/tangible/crafting/station/structure_tool.iff", price = 1500 },

			-- Survey tools
			{ template = "object/tangible/survey_tool/survey_tool_mineral.iff", price = 1000 },
			{ template = "object/tangible/survey_tool/survey_tool_liquid.iff", price = 1000 }, -- Chemical
			{ template = "object/tangible/survey_tool/survey_tool_lumber.iff", price = 1000 }, -- Flora
			{ template = "object/tangible/survey_tool/survey_tool_gas.iff", price = 1000 },
			{ template = "object/tangible/survey_tool/survey_tool_moisture.iff", price = 1000 }, -- Water
			{ template = "object/tangible/survey_tool/survey_tool_wind.iff", price = 1000 },
			{ template = "object/tangible/survey_tool/survey_tool_solar.iff", price = 1000 },

			-- Equipment
			{ template = "object/tangible/wearables/backpack/backpack_s01.iff", price = 1500 },
		},
	},
}
