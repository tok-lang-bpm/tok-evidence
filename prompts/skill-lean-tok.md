# tok modelling, lean skill

You turn a process description into a tok model and hand back a checked model.

1. Read the description. List the actors, the activities in their order, the decisions, the parallel work, and the start and the end of every path.
2. Write the model in tok: one pool for the organisation, one lane for each actor, one activity for each step named with the words of the description, `xor` for a decision with a label on every outgoing flow, `and` for parallel work with a matching join, a `start` event, and an `end` event on every path.
3. Call the tool `check` with the model as `text`. Every message names a code, a line and an element.
4. Fix every error and every warning and call `check` again, until the tool reports no errors and no warnings. Keep the model as small as the description allows.
5. Answer with the final model only, in one fenced code block marked ```tok.
