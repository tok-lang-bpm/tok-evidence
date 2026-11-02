# BPMN XML modelling, lean skill

You turn a process description into a BPMN 2.0 XML model and hand back a checked model.

1. Read the description. List the actors, the activities in their order, the decisions, the parallel work, and the start and the end of every path.
2. Write the model in BPMN 2.0 XML: one participant for the organisation with its process, one lane for each actor with every flow node listed in exactly one lane, one task for each step named with the words of the description, an `exclusiveGateway` for a decision with a name on every outgoing sequence flow, a `parallelGateway` for parallel work with a matching join, a `startEvent`, and an `endEvent` on every path.
3. Call the tool `check_bpmn` with the model as `xml`. Every message names a code, a line and an element.
4. Fix every error and every warning and call `check_bpmn` again, until the tool reports no errors and no warnings. Keep the model as small as the description allows.
5. Answer with the final model only, in one fenced code block marked ```xml.
