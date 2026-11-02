Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Building a custom machine out of Lego bricks

When building a custom machine out of Lego bricks, you first need to develop the basic design.
After that, you order certain Lego brick sets.
You give the lego sets to a group of children which should sort the parts for you (into a number of containers).
Your machine is built out of a number of subcomponents.
You build them individually, using parts from the sorted containers.
If there are no more parts in a container, you reorder individual parts.
After building each subcomponent, you have to test them individually and (if each test is successful) assemble them.
If subcomponents are not tested successfully, you have to redesign and rebuild them.
