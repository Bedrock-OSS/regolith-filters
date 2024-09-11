# Type Gen

This filter generates a `.d.ts` file that contains all the relevant constants in your add-on.

**Requires the [gametests](https://github.com/Bedrock-OSS/regolith-filters/tree/master/gametests) filter to be installed.**

## Data

1. Entities - All entity identifiers
2. Items - All item identifiers
3. Blocks - All block identifiers
4. Sounds - All sound identifiers
5. LangKeys - Language keys between `## #sync` and `## #endsync` lines in `en_US.lang`
6. Structures - All structure identifiers
7. LootTables - All loot table paths
8. Particles - All particle identifiers

## Getting the Filter

Install with: `regolith install type_gen`. After that, you can place the filter into one of your profiles. For the best results, you should run this filter as a last filter in your profile.

```json
{
    "filter": "type_gen"
}
```

## Usage

After running the filter at least once, you can import the generated `.d.ts` file in your project.

```ts
import { Entities } from './Files.d';
import { Dimension } from '@minecraft/server';

function spawnExampleEntity(dimension: Dimension) {
    return dimension.spawnEntity(Entities.Example);
}
```

## Settings

```json
{
  "outputFile": "Files.d.ts"
}
```

### outputFile

The output file to write the generated `.d.ts` file to. Defaults to `Files.d.ts`.

## Changelog

### 1.0.1

#55 Fixed issue where the filter would create an infinite loop when editing files in watch mode by @FrederoxDev

### 1.0.0

The first release of Type Gen.
