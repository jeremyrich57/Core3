--Should all created players start with God Mode? 1 = yes, 0 = no
freeGodMode = 0;
--How many cash credits new characters start with after creating a character (changed during test phase, normal value is 100)
startingCash = 5000
--startingCash = 100000
--How many bank credits new characters start with after creating a character (changed during test phase, normal value is 1000)
startingBank = 10000
--startingBank = 100000
--How many skill points a new characters start with
skillPoints = 250
--Starting attributes (HAM) of new characters are rescaled proportionally into this range.
--The lowest stat any species/profession combination can start with maps to attributeRangeMin,
--the highest to attributeRangeMax, and results are rounded to attributeRounding (adding up exactly to the
--species total). Only affects characters created after the change.
--Set attributeRangeMin and attributeRangeMax to 0 to use the client's original values.
--Stat migration limits come from datatables/creation/attribute_limits.iff, shared with the client. After
--changing these values, regenerate it and rebuild the patch (see patches/README.md):
--  python3 tools/patch/attribute_limits.py ~/tre && python3 tools/patch/build.py --install ~/tre
--If the file doesn't match these values, the server logs an error at startup and disables stat migration.
attributeRangeMin = 1600
attributeRangeMax = 2400
attributeRounding = 100

professions = {
	"combat_brawler",
	"combat_marksman",
	"crafting_artisan",
	"jedi",
	"outdoors_scout",
	"science_medic",
	"social_entertainer"
}

marksmanPistol = "object/weapon/ranged/pistol/pistol_cdef.iff"
	
marksmanRifle = "object/weapon/ranged/rifle/rifle_cdef.iff"

marksmanCarbine = "object/weapon/ranged/carbine/carbine_cdef.iff"

brawlerOneHander = "object/weapon/melee/knife/knife_stone.iff"

brawlerTwoHander = "object/weapon/melee/axe/axe_heavy_duty.iff"

brawlerPolearm = "object/weapon/melee/polearm/lance_staff_wood_s1.iff"

survivalKnife = "object/weapon/melee/knife/knife_survival.iff"

genericTool = "object/tangible/crafting/station/generic_tool.iff"

foodTool = "object/tangible/crafting/station/food_tool.iff"

mineralTool = "object/tangible/survey_tool/survey_tool_mineral.iff"

chemicalTool = "object/tangible/survey_tool/survey_tool_liquid.iff"

slitherhorn = "object/tangible/instrument/slitherhorn.iff"

marojMelon = "object/tangible/food/foraged/foraged_fruit_s1.iff"

x31Speeder = "object/tangible/deed/vehicle_deed/landspeeder_x31_deed.iff"

professionSpecificItems = {
	combat_brawler = { brawlerOneHander, brawlerTwoHander, brawlerPolearm },
	combat_marksman = { marksmanCarbine, marksmanRifle },
	crafting_artisan = { },
	jedi = { },
	outdoors_scout = { },
	science_medic = { foodTool },
	social_entertainer = { slitherhorn }
}

commonStartingItems = { marojMelon, survivalKnife, marksmanPistol, x31Speeder, genericTool, mineralTool, chemicalTool }