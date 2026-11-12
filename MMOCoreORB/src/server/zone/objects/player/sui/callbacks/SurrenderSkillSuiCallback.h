/*
				Copyright <SWGEmu>
		See file COPYING for copying conditions.*/

#ifndef SURRENDERSKILLSUICALLBACK_H_
#define SURRENDERSKILLSUICALLBACK_H_

#include "server/zone/objects/player/sui/SuiCallback.h"
#include "server/zone/objects/player/sui/listbox/SuiListBox.h"
#include "server/zone/managers/skill/SkillManager.h"

/**
 * Picking a skill from the /surrenderSkill list: asks to confirm surrendering it and everything that depends on it.
 */
class SurrenderSkillSelectSuiCallback : public SuiCallback {
public:
	SurrenderSkillSelectSuiCallback(ZoneServer* server) : SuiCallback(server) {
	}

	void run(CreatureObject* player, SuiBox* suiBox, uint32 eventIndex, Vector<UnicodeString>* args) {
		bool cancelPressed = (eventIndex == 1);

		if (player == nullptr || cancelPressed || !suiBox->isListBox() || args->size() <= 0)
			return;

		SuiListBox* listBox = cast<SuiListBox*>(suiBox);

		int index = Integer::valueOf(args->get(0).toString());

		if (index < 0 || index >= listBox->getMenuSize())
			return;

		Skill* skill = SkillManager::instance()->getSkill((uint32)listBox->getMenuObjectID(index));

		if (skill == nullptr)
			return;

		SkillManager::instance()->sendSurrenderSkillConfirm(player, skill->getSkillName());
	}
};

/**
 * Yes on the confirmation surrenders the skill and everything that depends on it.
 */
class SurrenderSkillConfirmSuiCallback : public SuiCallback {
	String skillName;

public:
	SurrenderSkillConfirmSuiCallback(ZoneServer* server, const String& skill) : SuiCallback(server) {
		skillName = skill;
	}

	void run(CreatureObject* player, SuiBox* suiBox, uint32 eventIndex, Vector<UnicodeString>* args) {
		bool cancelPressed = (eventIndex == 1);

		if (player == nullptr || cancelPressed)
			return;

		SkillManager::instance()->surrenderSkillCascade(skillName, player);
	}
};

#endif // SURRENDERSKILLSUICALLBACK_H_
