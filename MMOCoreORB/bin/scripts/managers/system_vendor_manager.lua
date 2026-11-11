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

-- Padded armor: +25 to every resist via armorBonus, then these set to a flat value
local paddedResists = { kinetic = 45, blast = 52 }

-- Bone armor: flat resists, these replace whatever the loot values give
local boneResists = { kinetic = 25, energy = 52, electricity = 44, heat = 33, acid = 33 }

systemVendors = {
	{
		key = "theed_quartermaster",
		planet = "naboo",
		template = "object/mobile/vendor/ithorian_male.iff",
		x = -4849,
		y = 4091,
		heading = 0,
		outfit = "VossQuartermaster",
		name = "",
		nameSpecies = "ithorian",
		title = "Quartermaster, Voss Syndicate",
		weaponAdjust = { speed = 0.6, damage = 1.15 },

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
