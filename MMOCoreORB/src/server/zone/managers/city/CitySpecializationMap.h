/*
 * CitySpecializationMap.h
 *
 *  Created on: Jul 20, 2012
 *      Author: swgemu
 */

#ifndef CITYSPECIALIZATIONMAP_H_
#define CITYSPECIALIZATIONMAP_H_

#include "CitySpecialization.h"

class CitySpecializationMap : public HashTable<String, CitySpecialization> {
	Vector<String> names; // Lua order, for menus.

public:
	inline const Vector<String>* getNames() const {
		return &names;
	}

	void readObject(LuaObject* luaObject) {
		if (!luaObject->isValidTable())
			return;

		for (int i = 1; i <= luaObject->getTableSize(); ++i) {
			LuaObject spec = luaObject->getObjectAt(i);

			if (spec.isValidTable()) {
				CitySpecialization citySpec;
				citySpec.readObject(&spec);

				if (!containsKey(citySpec.getName()))
					names.add(citySpec.getName());

				put(citySpec.getName(), citySpec);
			}

			spec.pop();
		}
	}
};

#endif /* CITYSPECIALIZATIONMAP_H_ */
