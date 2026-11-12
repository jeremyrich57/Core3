/*
				Copyright <SWGEmu>
		See file COPYING for copying conditions.*/

#ifndef REQUESTSETSTATMIGRATIONDATACOMMAND_H_
#define REQUESTSETSTATMIGRATIONDATACOMMAND_H_

#include "server/zone/objects/creature/CreatureObject.h"
#include "server/zone/objects/player/sessions/MigrateStatsSession.h"
#include "server/zone/managers/player/creation/PlayerCreationManager.h"

class RequestSetStatMigrationDataCommand : public QueueCommand {
public:
	RequestSetStatMigrationDataCommand(const String& name, ZoneProcessServer* server) : QueueCommand(name, server) {
	}

	static uint32 getMaxAttribute(CreatureObject* creature, uint8 attribute) {
		return PlayerCreationManager::instance()->getMaximumAttributeLimit(creature->getSpeciesName(), attribute);
	}

	static uint32 getMinAttribute(CreatureObject* creature, uint8 attribute) {
		return PlayerCreationManager::instance()->getMinimumAttributeLimit(creature->getSpeciesName(), attribute);
	}

	static uint32 getTotalAttribPoints(CreatureObject* creature) {
		return PlayerCreationManager::instance()->getTotalAttributeLimit(creature->getSpeciesName());
	}

	int doQueueCommand(CreatureObject* creature, const uint64& target, const UnicodeString& arguments) const {
		if (!checkStateMask(creature))
			return INVALIDSTATE;

		if (!checkInvalidLocomotions(creature))
			return INVALIDLOCOMOTION;

		if (!creature->isPlayerCreature()) {
			return GENERALERROR;
		}

		if (!PlayerCreationManager::instance()->isStatMigrationEnabled()) {
			creature->sendSystemMessage("Stat migration is not available on this server.");
			return SUCCESS;
		}

		auto ghost = creature->getPlayerObject();

		if (ghost == nullptr) {
			return GENERALERROR;
		}

		bool privilegedPlayer = ghost->isPrivileged();

		ManagedReference<Facade*> facade = creature->getActiveSession(SessionFacadeType::MIGRATESTATS);
		ManagedReference<MigrateStatsSession*> session = dynamic_cast<MigrateStatsSession*>(facade.get());

		if (session == nullptr) {
			return GENERALERROR;
		}

		StringTokenizer tokenizer(arguments.toString());
		tokenizer.setDelimeter(" ");

		uint32 targetPointsTotal = 0;
		uint32 targetAttributes[9] = {0,0,0,0,0,0,0,0,0};

		for (int i = 0; tokenizer.hasMoreTokens() && i < 9; ++i) {
			uint32 value = tokenizer.getIntToken();

			if (value < getMinAttribute(creature, i) || value > getMaxAttribute(creature, i)) {
				warning() << "Player: " << creature->getDisplayedName() << " ID: " << creature->getObjectID() <<  " --- Suspected stat migration hacking attempt.";
				return GENERALERROR;
			}

			targetAttributes[i] = value;
			targetPointsTotal += value;
		}

		// Here we set the stat migration target attributes.
		// NOTE: We aren't actually migrating the stats at this point.
		if (targetPointsTotal == getTotalAttribPoints(creature)) {
			for (int i = 0; i < 9; ++i) {
				session->setAttributeToModify(i, targetAttributes[i]);
			}
		} else {
			creature->error("targetPointsTotal = " + String::valueOf(targetPointsTotal));
			creature->error("totalAttribPoints = " + String::valueOf(getTotalAttribPoints(creature)));
			creature->error("Trying to set migratory stats without assigning all available points.");
			return GENERALERROR;
		}

		// Migration applies right away, anywhere, without an Image Designer, as long as the
		// player has full health, action and mind and no wounds or battle fatigue. Staff skip
		// the check.
		if (!privilegedPlayer && !isFullyHealed(creature)) {
			creature->sendSystemMessage("You can't migrate your stats until you're fully healed.");

			// Drop the pending targets so an Image Designer can't apply them past this check
			session->cancelSession();
			return SUCCESS;
		}

		session->migrateStats();

		if (privilegedPlayer) {
			creature->sendSystemMessage("Stat Migration Permitted due to Staff Privileges.");
		} else {
			creature->sendSystemMessage("Your stats have been migrated.");
		}

		return SUCCESS;
	}

	static bool isFullyHealed(CreatureObject* creature) {
		if (creature->getShockWounds() > 0)
			return false;

		for (int i = 0; i < 9; ++i) {
			if (creature->getWounds(i) > 0)
				return false;
		}

		// Health, action and mind pools
		for (int i = 0; i < 9; i += 3) {
			if (creature->getHAM(i) < creature->getMaxHAM(i))
				return false;
		}

		return true;
	}
};

#endif //REQUESTSETSTATMIGRATIONDATACOMMAND_H_
