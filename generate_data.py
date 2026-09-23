import os

# 1. Define topics.csv
topics = """topic_id,Topic,question_id,question
T01,CSIT x SWITCH x RISC Board Games Night Ticketing,T01Q01,Do I need an active club membership to buy tickets for the collaborative Board Games Night?
T01,CSIT x SWITCH x RISC Board Games Night Ticketing,T01Q02,Are non-members allowed to buy the discounted tickets for the joint CSIT SWITCH and RISC social event?
T02,RISC Free Membership Registration,T02Q01,How do I register for a free membership with the RMIT Information Security Collective?
T02,RISC Free Membership Registration,T02Q02,Where is the Hello Rubric sign up portal link for RISC located?
T03,REECE Hackathon Merchandise Pre-orders,T03Q01,What is the cancellation and refund policy for the REECE custom club hoodie pre-order?
T03,REECE Hackathon Merchandise Pre-orders,T03Q02,Can I get a refund on my REECE merchandise if I order the wrong size?
T04,MATRIX Math-Programming Comp Waiting List,T04Q01,How does the Hello Rubric waiting list work if the MATRIX coding event sells out?
T04,MATRIX Math-Programming Comp Waiting List,T04Q02,What happens when someone drops out of a fully reserved MATRIX algorithmic competition?"""

# 2. Define Collection.csv
collection = """passage_id,passage
P01,"For cross-club collaborative events like the CSIT x SWITCH x RISC Board Games Night, ticket purchases are strictly restricted to students holding an active membership with at least one of the hosting societies. The Hello Rubric platform checks your student SSO profile at checkout to automatically validate your membership status before completing the transaction."
P02,"Official club memberships for RISC (RMIT Information Security Collective) are fully funded this semester and cost $0. Students can claim their free membership instantly by navigating to the official Hello Rubric portal link hosted in the @rmit.risc Instagram link-in-bio page."
P03,"All REECE (RMIT Electronic Engineering and Computing Club) merchandise pre-orders are final once the manufacturing collection window closes on Rubric. Refunds or size exchanges are not provided for change of mind or user ordering errors, unless an item arrives with a verified physical manufacturing defect."
P04,"When a high-demand MATRIX computing competition reaches maximum capacity on Rubric, a 'Join Waiting List' button appears. If a registered student releases their ticket or fails to clear their order invoice within the allocated 15-minute checkout window, the ticket is instantly pushed down to the next user in line." """

# 3. Define groundtruth.csv
groundtruth = """topic_id,topic,passage_id,passage,relevance_judgment
T01,CSIT x SWITCH x RISC Board Games Night Ticketing,P01,"For cross-club collaborative events like the CSIT x SWITCH x RISC Board Games Night, ticket purchases are strictly restricted to students holding an active membership with at least one of the hosting societies. The Hello Rubric platform checks your student SSO profile at checkout to automatically validate your membership status before completing the transaction.",2
T02,RISC Free Membership Registration,P02,"Official club memberships for RISC (RMIT Information Security Collective) are fully funded this semester and cost $0. Students can claim their free membership instantly by navigating to the official Hello Rubric portal link hosted in the @rmit.risc Instagram link-in-bio page.",2
T03,REECE Hackathon Merchandise Pre-orders,P03,"All REECE (RMIT Electronic Engineering and Computing Club) merchandise pre-orders are final once the manufacturing collection window closes on Rubric. Refunds or size exchanges are not provided for change of mind or user ordering errors, unless an item arrives with a verified physical manufacturing defect.",2
T04,MATRIX Math-Programming Comp Waiting List,P04,"When a high-demand MATRIX computing competition reaches maximum capacity on Rubric, a 'Join Waiting List' button appears. If a registered student releases their ticket or fails to clear their order invoice within the allocated 15-minute checkout window, the ticket is instantly pushed down to the next user in line.",2"""

# 4. Define gold_summaries.csv
gold_summaries = """question_id,summary_id,summary,passage_id
T01Q01,P01,Yes. You must hold an active membership with either CSIT, SWITCH, or RISC to purchase a ticket. The Hello Rubric system automatically checks your student login credentials to confirm eligibility before checkout.,P01
T02Q01,P02,You can join RISC for free by visiting the official Hello Rubric registration platform link available directly inside the club's Instagram bio page.,P02
T03Q01,P03,REECE club merchandise pre-orders are non-refundable and final once the order window closes on Rubric. Refunds are only generated if a product is physically defective.,P03
T04Q01,P04,When a MATRIX event sells out on Rubric, joining the waiting list places you in line to automatically secure a spot if an order invoice expires or a user cancels their registration.,P04"""

# 5. Define qrels.txt
qrels = """T01Q01 0 P01 2
T01Q02 0 P01 2
T02Q01 0 P02 2
T02Q02 0 P02 2
T03Q01 0 P03 2
T03Q02 0 P03 1
T04Q01 0 P04 2
T04Q02 0 P04 2"""

# Ensure the output directory structure exists
os.makedirs("input", exist_ok=True)

# Write out the CSV files directly using standard text handling
with open("input/topics.csv", "w", encoding="utf-8") as f: f.write(topics)
with open("input/Collection.csv", "w", encoding="utf-8") as f: f.write(collection)
with open("input/groundtruth.csv", "w", encoding="utf-8") as f: f.write(groundtruth)
with open("input/gold_summaries.csv", "w", encoding="utf-8") as f: f.write(gold_summaries)

# Write the text evaluation framework file
with open("input/qrels.txt", "w", encoding="utf-8") as f: f.write(qrels)

print("All 5 evaluation dataset files successfully created in your input folder!")

