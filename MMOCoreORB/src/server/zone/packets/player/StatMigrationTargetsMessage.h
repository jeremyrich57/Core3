/*
				Copyright <SWGEmu>
		See file COPYING for copying conditions.*/

#ifndef STATMIGRATIONTARGETSMESSAGE_H_
#define STATMIGRATIONTARGETSMESSAGE_H_

#include "engine/service/proto/BaseMessage.h"

class StatMigrationTargetsMessage : public BaseMessage {
public:
	StatMigrationTargetsMessage(CreatureObject* creo) : BaseMessage() {
		insertShort(0x09);
		insertInt(0xEFAC38C4);  // CRC

		const DeltaVector<int>* baseHam = creo->getBaseHAM();

		// Normally 0, but characters whose stats don't add up to the species total (e.g. created
		// under different attribute rescaling) get the difference to redistribute.
		int totalLimit = PlayerCreationManager::instance()->getTotalAttributeLimit(creo->getSpeciesName());

		for (int i = 0; i < 9; ++i) {
			int val = baseHam->get(i);

			totalLimit -= val;

			insertInt(val);
		}

		insertInt(totalLimit); // Points Remaining

		setCompression(true);
	}

	StatMigrationTargetsMessage(CreatureObject* creo, MigrateStatsSession* stats) {
		insertShort(0x09);
		insertInt(0xEFAC38C4);  // CRC

		int totalLimit = PlayerCreationManager::instance()->getTotalAttributeLimit(creo->getSpeciesName());

		for (int i = 0; i < 9; ++i) {
			int val = stats->getAttribtueToModify(i);

			totalLimit -= val;

			insertInt(val);
		}

		insertInt(totalLimit);

		setCompression(true);
	}

};

#endif /*STATMIGRATIONTARGETSMESSAGE_H_*/
