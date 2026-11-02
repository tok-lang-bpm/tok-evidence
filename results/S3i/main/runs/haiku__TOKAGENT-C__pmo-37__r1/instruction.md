Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Contract

For your contract project you need parts from several web shops.
In order to find out which web shop has the right parts, you have to query them all, and find out how much they can deliver, at which price, and how long it will take.
Create a list of parts that you order from each shop.
If one shop has not enough  parts, order from several shops.
Always use the cheapest parts.
The parts arrive in batches in a random order, typically they are +/- 2 days earlier/later.
When the first parts arrive you start building.
Sometimes you have to reorder parts.
If your stock (for a single part) falls below 5, you reorder (the cheapest), if it falls below 3 you reorder again (the fastest).
If it is zero, you write a mail to your friends, complaining about the webshops.
