# FUSE-X Finality Runtime v1

FUSE-X owns durable observation, cursor, index and finality state. X is a replaceable authorized read-only sensor.

## Runtime chain

`authorized transport -> whoami -> home timeline -> atomic observation+cursor -> replay-safe idempotency -> restart reconstruction -> local search/index -> source verification -> derived feed -> X-loss continuity -> independent finality`

The source contains no post/reply/like/repost/follow/message/delete methods and grants no X account mutation authority. Credentials remain outside agent context. Personalized X access requires an owner-authorized X developer/application route and OAuth consent; source admission alone cannot satisfy that provider predicate.

Local/source proof must never be promoted into live-provider, recovery, value or finality maturity. Finality requires current provider-native readback plus recovery and independent Judge evidence.
