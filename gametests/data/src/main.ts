import {
  BlockLocation,
  system,
  TicksPerSecond,
  world,
} from '@minecraft/server';
import * as GameTest from '@minecraft/server-gametest';

system.runSchedule(() => {
  let player_count = world.getAllPlayers().length;
  if (player_count > 0) {
    world.say(`It has been ${system.currentTick / TicksPerSecond} seconds`);
  }
}, 100);

function simpleMobTest(test: GameTest.Test) {
  const attackerId = 'fox';
  const victimId = 'chicken';

  test.spawn(attackerId, new BlockLocation(3, 2, 3));
  test.spawn(victimId, new BlockLocation(2, 2, 2));

  test.assertEntityPresentInArea(victimId, true);

  // Succeed when the victim dies
  test.succeedWhen(() => {
    test.assertEntityPresentInArea(victimId, false);
  });
}

// Registration Code for our test
GameTest.register('StarterTests', 'simpleMobTest', simpleMobTest)
  .maxTicks(410)
  .structureName('gametests:test_5x5');
