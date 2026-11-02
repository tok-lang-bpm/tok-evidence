Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Farming Bot

Players want to create custom farming bots, that help them gather resources.
First you have to find out which resources you want.
Up to 10 resources in parallel can be collected, some resources are more urgently needed than others.
Some resources are required to create tools that are needed to gather other resources (create a custom logic of the dependencies in your game).
After all preferences are collected, your bot starts farming.
Sometimes,  random natural disasters strike and set your bot back.
Whenever some milestones are reached, you are notified.
During farming it is possible to update the list of to be farmed materials (at all times).
After the bot is finished, you should be able to brag to selected friends and/or send them materials.
