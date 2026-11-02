Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Instruct an artist to create a 3D model print it on a 3D printer

When craving a custom 3D model, as a first step you have to instruct an artist to create a project for you.
First you have to send him several sketches, and then tell him what to change until you are satisfied with the result.
After that, you choose a plastic color you want to use for 3D printing.
If you have the color at home (in stock), you check how much color you have left.
If it's under 100 grams, you put it on your shopping list.
If you do not have the color at home, you order it.
When you have the plastic, you can turn the printer on and heat up the bed and the extruder (it continuously sends you back its status).
While doing that, you can generate the gcode file for your printer out of the STL sent to you by the artist.
After that you print the model.
