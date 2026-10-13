from . import greedy, hungarian

ALGORITHMS = {
    greedy.NAME: greedy.allocate,
    "hungarian": hungarian.allocate_basic,
    "hungarian_deferred": hungarian.allocate_deferred,
}
