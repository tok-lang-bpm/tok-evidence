Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: LAN Party

You are planning a LAN party for 10 friends, so the first thing you have to do is to send invitations to these 10 friends.
Next, you have to find out which games they want to play.
As soon as you have received a list of games, you can appoint a date when the LAN party is going to happen.
If 8 or more people agree on this date, you are good to continue.
Else, you have to appoint another date, until 8 people are free to join you.
While you find a date, you can find out if you have all the games your guests want to play.
If some are missing, download them.
Next, you should find out how much beer your friends will require.
If you do not have enough, buy what's missing.
After that, you can enjoy the LAN party.
