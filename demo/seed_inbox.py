"""Generate a synthetic inbox for the public demo.

The real mailbox stays local. The deployed demo runs on this instead, so the
link can be shared without exposing anyone's actual mail - and because the
content is known, it can be used as ground truth for evaluation.

Persona: Alex Rivera, Operations Lead at Northwind Logistics (Seattle).
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path("data/demo_messages.jsonl")

# (days_ago, sender name, sender email, subject, body)
EMAILS = [
    (2, "Priya Raman", "priya.raman@northwind-log.com",
     "Q1 warehouse automation budget - need your sign-off",
     "Alex,\n\nFinance came back on the automation proposal. They'll approve the conveyor retrofit at the Tacoma site but want the robotics pilot deferred to Q2.\n\nThe retrofit is approved at 340,000 dollars with a hard completion date of March 14. Anything past that date rolls into next fiscal year and we lose the capital allocation.\n\nI need your sign-off by Friday November 28 so procurement can issue the PO.\n\nPriya"),

    (3, "Marcus Webb", "mwebb@claritysystems.io",
     "Re: Contract renewal - revised pricing",
     "Hi Alex,\n\nFollowing our call, here's where we landed. We can hold your current per-seat rate of 42 dollars if you commit to a 24-month term. For a 12-month renewal the rate moves to 51 dollars per seat.\n\nAt your current 180 seats that's a difference of about 19,000 dollars annually.\n\nThe current contract expires January 31. I'd need a signed order form two weeks before that to avoid a lapse in service.\n\nMarcus Webb\nClarity Systems"),

    (1, "Dana Osei", "dana.osei@northwind-log.com",
     "Incident 4471 - postmortem scheduled",
     "Team,\n\nPostmortem for the November 19 dispatch outage is Tuesday November 24 at 10am Pacific.\n\nRecap: the routing service went down at 2:14pm and we were degraded for 97 minutes. Root cause was a config push that doubled the connection pool timeout. 340 shipments delayed, 12 missed their SLA window.\n\nAction items so far: config changes need a second reviewer, and we need alerting on pool saturation rather than error rate.\n\nDana"),

    (5, "Jen Kowalski", "jen.kowalski@portauthority-sea.gov",
     "Dock scheduling change for December",
     "Alex,\n\nWe're changing dock allocation starting December 1. Northwind's slot of 6am-10am Tuesdays and Thursdays is moving to 5am-9am.\n\nThis is driven by the new rail interchange schedule. The earlier window should help your outbound timing but I know it affects crew shifts.\n\nAlternatives are Wednesday 11am-3pm or Friday 6am-10am. Let me know by November 26.\n\nJen Kowalski\nPort of Seattle"),

    (7, "Tomas Lindgren", "t.lindgren@nordhaul.se",
     "Partnership proposal - Scandinavian corridor",
     "Dear Alex,\n\nNordHaul is expanding our North American partnerships and Northwind came up repeatedly in our research.\n\nWe handle roughly 40 percent of freight volume between Gothenburg and the Baltic ports, and we're looking for a US West Coast partner for transpacific handoffs.\n\nWould you be open to an introductory call? I'm in Seattle the week of December 8 and could meet in person.\n\nBest regards,\nTomas Lindgren\nHead of Partnerships, NordHaul AB"),

    (4, "Rachel Ngo", "rachel.ngo@northwind-log.com",
     "Hiring update - two offers out",
     "Alex,\n\nStatus on the ops analyst roles:\n\nWe extended offers to both finalists. Samira Haddad accepted, starting December 15. Devon Park asked for until Monday - he has a competing offer and is negotiating on remote flexibility.\n\nIf Devon declines I'd rather reopen the search than go to our third candidate.\n\nBoth offers came in at the midpoint, 98,000 dollars.\n\nRachel"),

    (6, "IT Security", "security@northwind-log.com",
     "Mandatory: MFA migration deadline December 5",
     "All staff,\n\nWe're retiring SMS-based two-factor authentication on December 5. After that date SMS codes stop working and you will be locked out until you enroll an authenticator app.\n\nEnrollment takes about three minutes via the IT portal under Security Settings.\n\nThis affects everyone including contractors. 61 people have not yet enrolled.\n\nIT Security"),

    (8, "Linda Park", "lpark@freightwise-ins.com",
     "Insurance renewal - claims history review",
     "Hi Alex,\n\nAhead of the February renewal I've pulled your claims history. Three claims in 24 months totaling 87,000 dollars, below sector average for your fleet size.\n\nThat should put you in line for a modest premium reduction, maybe 4 to 6 percent.\n\nOne thing that would help: documentation of the driver safety program you rolled out in June. Underwriters weight that heavily. Can you send the training completion records?\n\nLinda"),

    (10, "Conference Team", "speakers@logisticsnw.org",
     "Speaker invitation - Logistics Northwest 2027",
     "Dear Alex Rivera,\n\nWe'd like to invite you to speak at Logistics Northwest, March 3-5 2027 in Portland.\n\nWe're building a track on warehouse automation adoption and your Tacoma retrofit work would be a strong fit. Format is a 30-minute talk plus 15 minutes of questions.\n\nWe cover travel and lodging. Confirmation needed by December 20 to finalize the program.\n\nLogistics Northwest Program Committee"),

    (2, "Samira Haddad", "samira.haddad.work@gmail.com",
     "Re: Offer - accepted, start date question",
     "Hi Alex,\n\nI signed the offer letter this morning.\n\nOne question on the start date. The letter says December 15 but I have a family commitment that week I can't move. Would January 5 work instead? I know that's a three-week delay.\n\nIf December matters I can make the 22nd work, though it's a short week.\n\nSamira"),

    (9, "Carlos Mendez", "cmendez@northwind-log.com",
     "Fleet maintenance - three trucks overdue",
     "Alex,\n\nUnits 112, 118, and 134 are past their scheduled maintenance intervals. 134 is the worst, about 4,200 miles over.\n\nPulling them for service drops Portland route capacity by roughly 20 percent for a week.\n\nOption B is staggering them over three weeks, which keeps capacity up but leaves 134 running overdue longer than I'm comfortable with.\n\nI'd recommend pulling 134 immediately and staggering the other two.\n\nCarlos"),

    (12, "Workday Notifications", "noreply@workday-notifications.com",
     "Your Q4 performance review is due",
     "This is an automated reminder.\n\nSelf-assessments for the Q4 review cycle are due December 12. Manager reviews are due December 19.\n\nYou have 6 direct reports with reviews pending.\n\nDo not reply to this message."),

    (3, "Elena Vasquez", "elena@greenpath-consulting.com",
     "Sustainability audit - preliminary findings",
     "Alex,\n\nPreliminary findings from the emissions audit.\n\nGood news: route optimization cut fleet emissions about 11 percent year over year, exceeding the 8 percent target.\n\nThe gap is facilities. Tacoma and Kent are both on standard grid power with no renewable procurement, now 64 percent of your reported scope 2 emissions.\n\nA renewable energy certificate purchase closes most of it for around 28,000 dollars annually. The alternative is onsite solar at Kent, roughly 400,000 dollars upfront with a seven-year payback.\n\nElena"),

    (14, "Devon Park", "devon.park.pm@outlook.com",
     "Re: Ops Analyst offer - decision",
     "Hi Rachel and Alex,\n\nThank you both for the offer and the time you spent with me.\n\nAfter a lot of thought I've decided to accept the other position. It came down to the remote policy - they're fully distributed and I'm relocating to Boise in the spring.\n\nI was genuinely impressed with the team and would be glad to stay in touch.\n\nDevon"),

    (1, "Priya Raman", "priya.raman@northwind-log.com",
     "Tacoma retrofit - vendor quotes compared",
     "Alex,\n\nThree quotes for the conveyor retrofit:\n\nAtlas Material Handling: 318,000 dollars, 11 week install, two sites our size already done.\n\nVertex Automation: 294,000 dollars, 9 weeks, cheapest but references were lukewarm on support responsiveness.\n\nKinetic Systems: 352,000 dollars, 10 weeks, strongest service agreement with a 24-hour response SLA.\n\nAll three fit the approved 340,000 except Kinetic, which is 12,000 over.\n\nI lean Atlas.\n\nPriya"),

    (5, "Facilities", "facilities@northwind-log.com",
     "Kent warehouse - roof repair scheduled",
     "Notice to all Kent warehouse staff.\n\nRoof repairs begin Monday December 1 and run approximately two weeks.\n\nBays 4 through 7 will be unavailable. Work happens 7am to 4pm weekdays. Expect noise.\n\nInventory in the affected bays must be relocated by Friday November 28.\n\nFacilities Team"),

    (11, "Nina Brandt", "nina.brandt@cascade-freight.com",
     "Capacity swap for the holidays?",
     "Alex,\n\nCascade is oversubscribed on the I-5 corridor the week of December 22 and we're short about 15 trailer loads.\n\nIf Northwind has slack that week I'd like to buy it, or swap against January capacity when we're typically lighter and you're not.\n\nWe've done this twice before and it worked well both times. I need to sort it by December 5.\n\nNina"),

    (6, "Legal", "legal@northwind-log.com",
     "Clarity Systems contract - review notes",
     "Alex,\n\nReviewed the Clarity renewal terms.\n\nThe 24-month commitment is fine but two clauses need pushback. Section 8.3 lets them raise rates at renewal with 30 days notice, which undercuts the rate lock. And the liability cap is three months of fees, low for a system this central to operations.\n\nRecommend asking for a 12-month notice period on rate changes and a cap at 12 months of fees.\n\nThey will likely concede the notice period and resist the cap.\n\nLegal Team"),

    (4, "Dana Osei", "dana.osei@northwind-log.com",
     "Routing service - monitoring improvements shipped",
     "Alex,\n\nShipped today: connection pool saturation alerting at an 80 percent threshold, and a required second approver on production routing config changes.\n\nStill open: the runbook rewrite and the load test for the new pool settings. Both should land by December 5.\n\nWe also found two other services with the same unreviewed-config-push risk. Not urgent but worth tracking.\n\nDana"),

    (16, "Amex Business", "noreply@americanexpress.com",
     "Your November statement is ready",
     "Your statement is now available.\n\nBalance and payment due date can be viewed by logging in to your account.\n\nThis is an automated notification."),

    (7, "Hiroshi Tanaka", "h.tanaka@pacificlink-jp.co.jp",
     "Transpacific volume forecast Q1",
     "Dear Alex,\n\nOur Q1 volume forecast for the Seattle-Yokohama lane projects a 14 percent increase over Q1 last year, driven by two new electronics clients. Peak weeks will be the second and third weeks of February.\n\nWe would like to confirm Northwind can absorb the additional volume on the drayage side. If capacity is tight please tell us early.\n\nWith regards,\nHiroshi Tanaka\nPacificLink Logistics"),

    (2, "Rachel Ngo", "rachel.ngo@northwind-log.com",
     "Devon declined - reopening the search",
     "Alex,\n\nDevon took the other offer. Remote policy was the deciding factor.\n\nI'd like to reopen rather than go to our third candidate, with two changes: post the role as hybrid rather than onsite, and raise the band ceiling to 108,000. We lost both our last two finalists on flexibility and comp.\n\nThat's a real budget ask so I wanted to raise it before going to Finance.\n\nRachel"),

    (9, "Training Portal", "training@northwind-log.com",
     "Forklift certification expiring - 8 staff",
     "Automated compliance notice.\n\nEight warehouse staff have forklift certifications expiring within 60 days. Operating without current certification is an OSHA violation.\n\nThe next onsite certification session is December 9 at the Kent facility. Capacity is 12 people.\n\nShift leads should register affected staff through the training portal."),

    (13, "Greg Mallory", "gmallory@northwind-log.com",
     "Budget variance - October close",
     "Alex,\n\nOctober is closed. Ops came in 4.2 percent under budget, mostly lower fuel costs than forecast.\n\nTwo variances worth noting. Overtime ran 31,000 dollars over, concentrated at Kent during the mid-month volume spike. Maintenance was 18,000 under, which given Carlos's overdue-truck email is probably deferred cost rather than savings.\n\nGreg"),

    (3, "Jen Kowalski", "jen.kowalski@portauthority-sea.gov",
     "Re: Dock scheduling - confirming Friday option",
     "Alex,\n\nConfirming the Friday 6am-10am slot for Northwind starting December 1.\n\nI'll update the allocation system today. You should see it in the terminal portal within 48 hours.\n\nOne note: Fridays before holidays run congested, December 19 and 26 specifically. Build in buffer.\n\nJen"),

    (8, "Marcus Webb", "mwebb@claritysystems.io",
     "Re: Contract renewal - on the liability cap",
     "Alex,\n\nTook your redlines to our legal team.\n\nWe can agree to the 12-month notice period on rate changes. I've got approval for that.\n\nThe liability cap is harder. Twelve months of fees is well outside our standard. The most I can get approved is six months.\n\nIf six months works I can have a clean order form to you by Wednesday.\n\nMarcus"),

    (18, "LinkedIn", "notifications@linkedin.com",
     "You appeared in 47 searches this week",
     "Your profile is getting noticed.\n\nSee who's viewing your profile and what searches you appeared in.\n\nManage notification preferences in settings."),

    (5, "Carlos Mendez", "cmendez@northwind-log.com",
     "Unit 134 pulled - capacity impact",
     "Alex,\n\nPulled 134 this morning. Shop found a cracked leaf spring, so good timing - would have been a roadside failure within a few weeks.\n\nBack in service Thursday. Covering Portland with a rental meanwhile, 1,400 dollars for the week.\n\n112 and 118 scheduled for December 2 and December 9.\n\nCarlos"),

    (11, "Elena Vasquez", "elena@greenpath-consulting.com",
     "Re: RECs vs onsite solar - my recommendation",
     "Alex,\n\nYou asked which way I'd go. Short answer: renewable energy certificates now, solar study later.\n\nThe RECs close your scope 2 gap immediately at a predictable annual cost, and your reporting deadline is March.\n\nSolar at Kent is a good long-term investment but a seven-year payback needs a matching lease horizon, and Kent's lease runs through 2031. Tight but workable if you decide within 18 months.\n\nDoing RECs now doesn't foreclose solar later.\n\nElena"),

    (1, "Nina Brandt", "nina.brandt@cascade-freight.com",
     "Re: Capacity swap - revised ask",
     "Alex,\n\nUnderstood on December 22. Let me revise.\n\nCould you do 8 loads instead of 15? That covers our worst days.\n\nI'd swap against the week of January 12, where we run well under capacity and I know you're usually crunched post-holiday.\n\nIf 8 is still too many, tell me what number works.\n\nNina"),

    (15, "Office Admin", "admin@northwind-log.com",
     "Holiday party - December 18",
     "Everyone,\n\nThe holiday party is December 18, 6pm at the Maritime Hall in Ballard.\n\nPlus-ones welcome. Please RSVP through the intranet by December 8 so we can finalize catering.\n\nDietary restrictions can be noted in the RSVP form.\n\nOffice Admin"),

    (6, "Priya Raman", "priya.raman@northwind-log.com",
     "Re: Atlas selected - timeline risk",
     "Alex,\n\nAtlas is confirmed, PO goes out Monday.\n\nOne risk for the record. Their 11-week install means completion around February 20, leaving only three weeks of buffer before the March 14 capital deadline. Any slip eats that fast.\n\nI've asked Atlas for a weekly status call and milestone dates in writing. If we're not at 50 percent by January 10 we should escalate.\n\nPriya"),

    (10, "Dr. Amara Okonkwo", "aokonkwo@uw.edu",
     "Research collaboration - warehouse ergonomics study",
     "Dear Mr. Rivera,\n\nI lead the industrial ergonomics group at the University of Washington. We're starting a two-year study on injury prevention in high-throughput warehouse environments.\n\nWe're looking for three to four industry partners. Participation means allowing observational researchers onsite for roughly 20 days across the study, and sharing anonymized injury incidence data.\n\nPartners receive findings before publication and site-specific recommendations at no cost.\n\nDr. Amara Okonkwo"),

    (4, "Greg Mallory", "gmallory@northwind-log.com",
     "Re: Rachel's band increase request",
     "Alex,\n\nOn the ops analyst band ceiling. I can support 108,000 but there's a knock-on effect - four analysts already in seat sit below that number, and raising the band for new hires creates an equity problem.\n\nIf we do this I'd want about 22,000 dollars budgeted for internal adjustments at the same time. Otherwise we're setting up a retention risk.\n\nThat makes the real ask 130,000, not the 10,000 delta it looks like on paper.\n\nGreg"),

    (7, "Shipping Notifications", "tracking@parcelforce-us.com",
     "Your shipment has been delivered",
     "Your package was delivered Thursday at 2:47pm. Left at front door.\n\nTrack additional shipments through your account dashboard."),

    (12, "Tomas Lindgren", "t.lindgren@nordhaul.se",
     "Re: Seattle meeting - December 9 or 10?",
     "Alex,\n\nGlad you're interested. I have December 9 and 10 available.\n\nMy preference is the morning of the 9th, which leaves time to visit the Tacoma site in the afternoon if useful. I'd genuinely like to see the operation.\n\nI'm staying downtown so Seattle or Tacoma both work.\n\nTomas"),

    (2, "Dana Osei", "dana.osei@northwind-log.com",
     "Load test results - pool settings validated",
     "Alex,\n\nLoad test done. New connection pool settings held at 3x our peak observed traffic with no saturation. The old settings degraded at 1.4x, which explains the incident.\n\nRunbook rewrite is complete and in the wiki.\n\nThat closes all action items from incident 4471 except the two other services I flagged. Tickets opened but not scheduled.\n\nDana"),

    (9, "Linda Park", "lpark@freightwise-ins.com",
     "Re: Safety program docs received",
     "Hi Alex,\n\nGot the training records, thank you. 94 percent completion is strong and the underwriters will like it.\n\nBased on what I'm seeing I'd now estimate a 6 to 8 percent premium reduction, better than my earlier guess.\n\nFormal quote mid-December. Renewal is February 1 so we have room.\n\nLinda"),

    (3, "Hiroshi Tanaka", "h.tanaka@pacificlink-jp.co.jp",
     "Re: Drayage capacity confirmation needed",
     "Dear Alex,\n\nOur clients are asking us to confirm arrangements by December 15. If Northwind can commit to the additional drayage capacity for February peak weeks, we would like to formalize it.\n\nIf capacity is uncertain, please tell us now rather than later. We can arrange a secondary provider but need lead time.\n\nWith regards,\nHiroshi Tanaka"),

    (6, "Samira Haddad", "samira.haddad.work@gmail.com",
     "Re: January 5 start confirmed - onboarding question",
     "Hi Alex,\n\nThank you for accommodating the January 5 start.\n\nTwo onboarding questions. Is there reading you'd recommend before I start? I'd like context on the routing systems rather than learning cold.\n\nAlso, will I be based at Kent or Tacoma? The offer letter said Kent but the role description mentioned Tacoma site work.\n\nSamira"),
]


def rfc_date(days_ago):
    dt = datetime.now(timezone.utc) - timedelta(
        days=days_ago, hours=days_ago % 7, minutes=days_ago * 7 % 60
    )
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def main():
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w") as f:
        for i, (days, name, addr, subject, body) in enumerate(EMAILS):
            mid = hashlib.sha1(f"{i}{subject}".encode()).hexdigest()[:16]
            f.write(json.dumps({
                "id": mid,
                "thread_id": mid,
                "subject": subject,
                "from": f"{name} <{addr}>",
                "date": rfc_date(days),
                "body": body,
            }) + "\n")
    print(f"Wrote {len(EMAILS)} synthetic messages to {OUT}")


if __name__ == "__main__":
    main()
