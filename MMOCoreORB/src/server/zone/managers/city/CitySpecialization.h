/*
 * CitySpecialization.h
 *
 *  Created on: Jul 20, 2012
 *      Author: swgemu
 */

#ifndef CITYSPECIALIZATION_H_
#define CITYSPECIALIZATION_H_

class CitySpecialization : public Object {
	String name;
	String description; // Custom text for specs without a client STF entry (otherwise name + "_d" is used).
	int cost;
	VectorMap<String, int> skillMods;
	Vector<String> requiredAbilities; // Upgrade specs: offered only when the mayor has every listed city_spec_* ability.

public:
	CitySpecialization() {
		cost = 0;
		skillMods.setNoDuplicateInsertPlan();
		skillMods.setNullValue(0);
	}

	CitySpecialization(const String& name, int cost) {
		this->name = name;
		this->cost = cost;
	}

	CitySpecialization(const CitySpecialization& spec) : Object() {
		name = spec.name;
		description = spec.description;
		cost = spec.cost;
		skillMods = spec.skillMods;
		requiredAbilities = spec.requiredAbilities;
	}

	CitySpecialization& operator=(const CitySpecialization& spec) {
		if (this == &spec)
			return *this;

		name = spec.name;
		description = spec.description;
		cost = spec.cost;
		skillMods = spec.skillMods;
		requiredAbilities = spec.requiredAbilities;

		return *this;
	}

	void readObject(LuaObject* luaObject) {
		name = luaObject->getStringField("name");
		description = luaObject->getStringField("description");
		cost = luaObject->getIntField("cost");

		LuaObject reqs = luaObject->getObjectField("requires");

		if (reqs.isValidTable()) {
			for (int i = 1; i <= reqs.getTableSize(); ++i)
				requiredAbilities.add(reqs.getStringAt(i));
		}

		reqs.pop();

		LuaObject smods = luaObject->getObjectField("skillMods");

		for (int i = 1; i <= smods.getTableSize(); ++i) {
			LuaObject mod = smods.getObjectAt(i);

			if (mod.isValidTable()) {
				String k = mod.getStringAt(1);
				int v = mod.getIntAt(2);

				skillMods.put(k, v);
			}

			mod.pop();
		}

		smods.pop();
	}

	inline const String& getName() const {
		return name;
	}

	inline const String& getDescription() const {
		return description;
	}

	inline bool isUpgrade() const {
		return requiredAbilities.size() > 0;
	}

	inline const Vector<String>* getRequiredAbilities() const {
		return &requiredAbilities;
	}

	inline int getCost() const {
		return cost;
	}

	inline const VectorMap<String, int>* getSkillMods() const {
		return &skillMods;
	}
};

#endif /* CITYSPECIALIZATION_H_ */
