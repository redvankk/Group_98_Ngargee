# Group_98_Ngargee
## Contributors

| Name                         | Student ID |
| ---------------------------- | ---------- |
| Maristel Moralejo-Feliciano  | s3992004   |
| Md Tashfiq Haque Choudhury   | s4200380   |
| Mohamed Ridhwan Mansoor      | s4203049   |
| Spoorthi Mallik Mallikarjuna | s4203196   |
| Navan   Kamalakanthan        | s4219963   |
| Meghana Ramachandraiah       | s4224049   |

## Requirements
- python 3.10.8
- Install all packages in 'requirements.txt' using:
```
   cd Group_98_Ngargee/quantitative_eval
   pip install -r requirements.txy
```

## Data 
All dataset files are located in the `data` folder, which includes files that are generated from RMIT University Student Union (RUSU) website, each club's official website, and social media channels, such as Instagram, Facebook, LinkedIn, Discord, Linktree, and Rubric Club Page. The files include:

1. **File Name: club.csv**\
   -*Format:* CSV\  
   -*Description:* This dataset contains high-level, general information about each computing  club. It is optimised for users searching for new clubs or trying to understand what each club does. It contains unique club ID, name, acronym, category, description, and campus location.\
   -*Columns:*
     - `club_index`: Unique ID for each club (e.g., CI05)
     - `club_name`: Name of the RUSU affiliated club as it appears in the RUSU website (e.g., RMIT Matrix)
     - `club_acronym`: Unique acronym for each club (e.g., Matrix)
     - `category`: Club category based on RUSU classification (e.g., Social and Special Interest)
     - `description`: Description of each club as it appears in the Rubric club page, club official website, and/ or social media channels. (e.g., RMIT Matrix is a club for Competitive Programming & Algorithms. We solve algorithmic problems, train for contests like ICPC, and get sharper together, whatever your starting point.  No competitive background needed. MATRIX is open to every RMIT student. Plenty of us started knowing nothing about competitive programming. What matters is the curiosity to pick apart a hard problem and the patience to learn the techniques. Beginners are genuinely welcome. We are affiliated with the RMIT University Student Union (RUSU) and run by a volunteer committee. We focus on algorithmic problem-solving and contest training, a niche the general CS clubs do not fill.)
     - `rmit_university_campus`: RMIT University campus (e.g., City Campus)
 
Total clubs: 5 of 5 RUSU-affiliated whhich are computing-related clubs.


2. **File Name: membership.csv**\
   -*Format:* CSV\
   -*Description:* This dataset indicates membership tiers offered by each club. It is utilised for membership eligibility and restrictions.\
   -*Columns:*
     - `club_acronym`: Unique acronym for each club (e.g., RISC).
     - `full_membership': The highest membership tier for currently enrolled RMIT students, subject to additional eligibility criteria for each club (e.g., Full voting rights at general meetings, must be an RMIT student and study a Technology/ IT / Cyber related degree.)
     - `associate_membership`: This membership tier is for people interested to join the club who are not currently enrolled at RMIT. (e.g., Open to Alumni, RMIT Staff, students from other universities and the general public.)
     - `under_18_membership`: Membership category for under 18 years old members (e.g., This membership is for our under 18 years old members! You may be restricted from attending 18+ events and may need a parental consent to attend events. Your membership will be upgraded on your birthday.)
     - `social_membership`: This tier is for members who do not meet eligibility requirements for full membership (e.g., Open to all current RMIT Students.)


3. **File Name: executive.csv**\
   -*Format*: CSV\
   -*Description*: This contains the executive and operational positions and elected officers for each club and the official club email address. The officers change annually during the Annual General Meeting. \
   -*Columns*:
     - `club_name`: Name of the RUSU affiliated club as it appears in the RUSU website (e.g., RMIT Matrix)
     - `club_email`: The official RMIT club email address (e.g., matrix@rmit.edu.au)
     - `president`: Name of elected president
     - `vice_president`: Name of elected vice president
     - `vice_president_operations`: Name of elected vice president of operations
     - `vice_president_administration`: Name of elected vice president of administration
     - `secretary`: Name of elected secretary
     - `treasurer`: Name of elected treasurer
     - `social_media_manager`: Name of elected social media manager 
     - `sponsorship_officer`: Name of elected sponsorship officer
     - `events_officer`: Name of elected events officer

4. **File Name: social.csv**\
   -*Format*: CSV\
   -*Description*: This is the digital map of the club ecosystem. It is multi-purpose, it answers user queries about where to find club specific things online, it directs users to the official email address, and it provides the raw seeding URLs for the dynamic web-scraping pipelines. This includes RMIT email address, website, rubric page, and social media channels which links to their events page. \
   -*Columns*:
     - `club_email`: The official RMIT club email address (e.g., matrix@rmit.edu.au)
     - `instagram`: Link to club Instagram (e.g., https://www.instagram.com/matrix.rmit/) 	 		
     - `facebook`: Link to club Facebook page (e.g., https://www.facebook.com/people/RMIT-Matrix/61579640997617/) 
     - `linkedin`: Link to club LinkedIn page (e.g., https://www.linkedin.com/company/rmit-matrix/)
     - `discord`: Link to club Discord server(e.g., https://discord.com/invite/Fm8s2en9mY)
     - `linktree`: Link to club Linktree (e.g., https://linktr.ee/matrix.rmit)
     - `website`: Link to club website (e.g., https://rmitmatrix.com/)	
     - `rubric_page`: Link to club Rubric page (e.g., https://campus.hellorubric.com/?s=14937)
  
5. **File Name: query.csv**\
   -*Format*: CSV\
   -*Description*: Frequently asked questions and user story related queries are in this dataset along with the answers\
   -*Columns*:
     - `topic_id`: Unique topic ID (e.g., TI01)
     - `topic`:  (e.g.,computing related clubs)
     - `question_id`: Unique question ID (e.g., QI01)
     - `question`: (e.g., How many computing clubs are there?)
     - `answer`: (e.g., There are 5 computing related clubs at RMIT.)
  ** NOTE: generate_data.py is a dummy set
