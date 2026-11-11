/*
 * VendorZoneComponent.h
 *
 *  Created on: Jul 24, 2012
 *      Author: kyle
 */

#ifndef VENDORZONECOMPONENT_H_
#define VENDORZONECOMPONENT_H_

#include "server/zone/objects/scene/components/GroundZoneComponent.h"
#include "server/zone/objects/tangible/components/vendor/VendorDataComponent.h"
#include "server/zone/TreeEntry.h"

class VendorZoneComponent : public GroundZoneComponent {

public:
	void notifyPositionUpdate(SceneObject* sceneObject, TreeEntry* entry) const {
		ManagedReference<SceneObject*> target = cast<SceneObject*>(entry);

		if (target == nullptr || !target->isPlayerCreature()) {
			return;
		}

		VendorDataComponent* data = cast<VendorDataComponent*>(sceneObject->getDataObjectComponent()->get());

		if (data == nullptr || !data->isAdBarkingEnabled())
			return;

		float distanceSq = target->getWorldPosition().squaredDistanceTo2d(sceneObject->getWorldPosition());

		// System vendors greet each player once on approach, and again only after the
		// player has walked well away. A short shared cooldown keeps crowds from spamming.
		if (data->hasGreeting()) {
			const uint64 targetID = target->getObjectID();
			const float range = data->getGreetingRange();
			const float forgetRange = range + VendorDataComponent::GREETFORGETRANGE;

			if (distanceSq < range * range) {
				if (!data->hasBarkTarget(targetID) && data->canGreet())
					data->performVendorBark(target);
			} else if (distanceSq > forgetRange * forgetRange && data->hasBarkTarget(targetID)) {
				data->removeBarkTarget(targetID);
			}

			return;
		}

		float checkSq = VendorDataComponent::BARKRANGE * VendorDataComponent::BARKRANGE;

		if (distanceSq < checkSq) {
			if (data->canBark()) {
				data->performVendorBark(target);
			} else {
				data->addBarkTarget(target->getObjectID());
			}
		} else if (data->hasBarkTarget(target->getObjectID())) {
			data->removeBarkTarget(target->getObjectID());
		}
	}
};

#endif /* VENDORZONECOMPONENT_H_ */
