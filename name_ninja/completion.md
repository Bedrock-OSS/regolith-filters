# Name Ninja

This filter is used to automatically generate entity, block, spawn egg, and item names, based on a custom 'name' field, or on the entities identifier.

Simply add a `name` field into the description of a file:

```jsonc
{
  "format_version": "1.17.0",
  "minecraft:entity": {
    "description": {
      "identifier": "sirlich:frog",
      "name": "🐸 South American Horned Toad",
      "is_spawnable": true,
      "is_summonable": true,
      "is_experimental": false,
    },
    // rest of file
}
```

This will add a translation line such as: `entity.sirlich:frog.name=🐸 South American Horned Toad   ## Generated via Regolith` to your language file of choice.