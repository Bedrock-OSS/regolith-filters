import { world } from 'mojang-minecraft';
import * as GameTest from 'mojang-gametest';
import { BlockLocation } from 'mojang-minecraft';

world.events.tick.subscribe((tick_event) => {
  let should_trigger = tick_event.currentTick % 100 == 0;
  let player_count = [...world.getPlayers()].length;
  if (should_trigger && player_count > 0) {
    let seconds = tick_event.currentTick / 20;
    world
      .getDimension('overworld')
      .runCommand(
        `tellraw @a {"rawtext":[{"text":"It has been ${seconds} seconds"}]}`
      );
  }
});

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
