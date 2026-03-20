// All data as of: 19 March 2026, 10 AM
import { useState, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from "recharts";

const CLUSTERS = [
  {
    id: "vadner", name: "Vadner Bhairav", region: "Chandwad",
    total: 183.71, paid: 183.71, done: 31.5, pending: 152.21,
    deposits: 632676, farmers: 38, health: "critical",
    deployed: [
      { team: "Digambar Pawar", members: 22, type: "permanent", status: "working", farmer: "Balaji Patole / Arun Shinde", note: "Arrived 13 Mar. Stationed at Nivrutti Shinde shed. Consistent since arrival. Tata Strive team visited 18 Mar — impressed." },
      { team: "Yashwant Shevare", members: 30, type: "permanent", status: "working", farmer: "Suresh Pachorkar / Shinde group", note: "ARRIVED 15 Mar. Biggest team. Stationed at Sudarshan Bhalerao shed. Salukhe shed full (harvesting crew)." },
    ],
    pipeline: [
      { name: "Vinod Wagh (15)", eta: "20 Mar", conf: 65, note: "Postponed from 17th to 20th. Agent from Sakri. Rate ₹17,500. Not ready for paste-only work." },
    ],
    sheds: "Nivrutti Shinde (20 cap), Bapusaheb Salukhe (25 cap — occupied by harvesters), Sudarshan Bhalerao, Suresh Pachorkar (20 cap — inspected 16 Mar), Jagannath Nikam Govarthan (3 rooms, 20 cap, 12km from Vadner)",
    alerts: [
      "183ac — LARGEST cluster. 52 laborers on ground (Digambar 22 + Shevare 30). 31.5ac done (17%).",
      "Shevare arrival on 15th was TRANSFORMATIVE. 30 PAX biggest team in network.",
      "Pending of 18th: Amol Nikam, Balaji Patole, Valuba Gachale — queue managed.",
      "Jaywant Shinde (Dewargaon) 8.75ac — FIRST-EVER customer. Wife passed away. Azhaan: 'We owe it to him.' Prioritize.",
      "Salukhe shed unavailable — 15 harvesters occupying it. Temporary accommodation arranged.",
      "Hemraj Kadali (up-down) missed 17 Mar — driver had accident. Unreliable transport dependency.",
    ],
  },
  {
    id: "sinner", name: "Sinner (All Sub-Clusters)", region: "Sinner",
    total: 103.3, paid: 103.3, done: 36.05, pending: 67.25,
    deposits: 273747, farmers: 25, health: "warning",
    deployed: [
      { team: "Khandu Kamdi", members: 10, type: "permanent", status: "working", farmer: "Kolhewadi (moved 18 Mar)", note: "Moved from Chikani→Kolhewadi 18 Mar. ₹1200 transport. Chikani done (3.75ac). Kolhewadi plots were wet, now dry." },
      { team: "Janardhan Bhoye", members: 23, type: "stationed", status: "working", farmer: "Ravindra Tukaram Borade (Pandhurli)", note: "12.7ac done at Pandhurli. Best shed (70 cap). Cordon tying started for Ravindra Borade." },
    ],
    pipeline: [],
    subClusters: [
      { name: "Chikani-Sangamner", acres: 28.05, team: "Khandu Kamdi completed 3.75ac", status: "PARTIAL — harvesting ongoing, date postponed" },
      { name: "Pandhurli", acres: 27.2, team: "Bhoye (23)", status: "WORKING — 12.7ac done, cordon tying started" },
      { name: "Kolhewadi", acres: 19.5, team: "Khandu Kamdi (10)", status: "WORKING from 18 Mar — Tushar Dighe 19.5ac" },
      { name: "Vadgaon Landga", acres: 9.35, team: "Khandu Kamdi after Kolhewadi", status: "7.1ac DONE — 2.25ac remaining" },
      { name: "Konambe", acres: 4, team: "Bhoye completed", status: "COMPLETED ✓" },
      { name: "Chas", acres: 2.5, team: "Done", status: "COMPLETED ✓" },
      { name: "Harsule", acres: 2.5, team: "Vitthal Pawar completed", status: "COMPLETED ✓" },
      { name: "Bhojapur", acres: 6.7, team: "None", status: "April case" },
      { name: "Jawale Kadalak", acres: 1.5, team: "Done", status: "COMPLETED ✓" },
      { name: "Nalwadi", acres: 2, team: "Done", status: "COMPLETED ✓" },
    ],
    sheds: "Pandhurli/Ravindra Borade (70 cap — best in network), Jaydev Varpe/Chikani (15-18 cap)",
    alerts: [
      "36ac completed (35%) — massive improvement from 9.75ac on 13 Mar. 5 sub-clusters DONE.",
      "Konambe, Chas, Harsule, Jawale Kadalak, Nalwadi — all completed.",
      "Khandu Kamdi successfully moved to Kolhewadi (Tushar Dighe 19.5ac).",
      "Bhojapur 6.7ac — April pruning, no urgency.",
      "Vadgaon Landga nearly done (7.1 of 9.35ac).",
    ],
  },
  {
    id: "dindori", name: "Dindori", region: "Dindori",
    total: 100.25, paid: 100.25, done: 23.75, pending: 76.5,
    deposits: 48150, farmers: 8, health: "critical",
    deployed: [
      { team: "Pushparaj Kadali", members: 15, type: "stationed", status: "working", farmer: "Mohadi / MRDBS", note: "MRDBS 6.25ac done (was 0 on 13 Mar!). Moved to Mohadi 18 Mar for Dhananjay Jadhav. Vijay Kalamkar frustrated — team scheduling confusion." },
      { team: "Umesh Khambait", members: 9, type: "permanent", status: "working", farmer: "Jawalke Vani (Prakash Dawange)", note: "NEW team finalized 17 Mar. ₹20,200 rate. 5K advance paid. 3 more workers may join. Deployed to Jawalke Vani." },
    ],
    pipeline: [
      { name: "Pandurang Deshmukh", eta: "19-20 Mar", conf: 70, note: "New lead sourced 18 Mar. For Khadak Ozar overflow or Dindori cordon tying." },
      { name: "Yashwant Shevare extended team (Dindori)", eta: "TBD", conf: 40, note: "Shevare has up-down team in Dindori not yet on tender. Animesh exploring." },
    ],
    subClusters: [
      { name: "Talegaon Vani", acres: 23, team: "No active team", status: "15ac done. Vilas Pawar up-down (Chaure)" },
      { name: "Vani/Kasbe Vani", acres: 16.75, team: "Pushparaj Kadali (prior)", status: "7.5ac done. Cordon tying no team — Anil Kad frustrated" },
      { name: "MRDBS Talegaon", acres: 14, team: "Pushparaj Kadali", status: "6.25ac DONE — Avinash Chopde 1ac. PARTIALLY RECOVERED" },
      { name: "Jawalke Vani", acres: 25.5, team: "Umesh Khambait (9)", status: "4ac done. Vitthal Pawar + Umesh Khambait working" },
      { name: "Mohadi", acres: 22.65, team: "Pushparaj Kadali (18 Mar)", status: "2.5ac done. Vijay Kalamkar 17.75ac — farmer very frustrated" },
      { name: "Nilwandi", acres: 6.8, team: "Team required 20th per Ramdas ji", status: "PLANNED — 0ac done" },
      { name: "Sonjamb", acres: 1.55, team: "None — 19th target", status: "NO TEAM" },
      { name: "Indore", acres: 2, team: "None", status: "Pruning done by farmer himself" },
      { name: "Pade", acres: 2, team: "None", status: "Gorakh Pawar 2ac" },
    ],
    sheds: "Prakash Dawange/Jawalke Vani (20 cap rooms + 30 cap shed — inspected 14 Mar), Anil Kad/Vani (20 cap)",
    alerts: [
      "100ac across 9 sub-clusters. 23.75ac done (24%) — up from 10ac on 13 Mar.",
      "MRDBS PARTIALLY RECOVERED: 6.25ac done including Avinash Chopde. Relationship partially salvaged.",
      "Vijay Kalamkar (Mohadi) FRUSTRATED — team scheduled for 18th didn't show (Vitthal Pawar no-show again).",
      "Anil Kad cordon tying STILL UNRESOLVED — Rohan escalating. Need female team or new permanent team.",
      "Umesh Khambait (9) is new permanent team — deployed to Jawalke Vani. Could grow to 12.",
      "Talegaon Vani 15ac done — good progress. Vilas Pawar up-down working intermittently.",
    ],
  },
  {
    id: "khadak", name: "Khadak Ozar", region: "Chandwad",
    total: 39.68, paid: 39.68, done: 16.5, pending: 23.18,
    deposits: 0, farmers: 9, health: "warning",
    deployed: [
      { team: "Ramesh Pithe (split)", members: 13, type: "split", status: "working", farmer: "Nivrutti Pagar / Pandurang Deshmukh", note: "Main squad back at KO. 16.5ac done (42%). Working through remaining farmers sequentially." },
    ],
    pipeline: [
      { name: "Pandurang Deshmukh", eta: "19-20 Mar", conf: 70, note: "New team sourced by Roshan 18 Mar. For KO if Pithe overloaded." },
    ],
    sheds: "Dnyaneshwar Pagar (15 cap), Bhausaheb Pagar (15 cap, max 15 per farmer request)",
    alerts: [
      "16.5ac done (42%) — up from 7.25ac on 13 Mar. Good progress.",
      "Farmers with plots ready since 5-10 Mar now being served: Dattu Pagar, Yogesh Pagar in queue.",
      "Pithe females (5) + main team working. Cordon tying margin issue resolved (0% margin approved).",
      "Shed constraint persists: both locations max 15. Large team cannot be accommodated.",
    ],
  },
  {
    id: "pgarud", name: "P. Garudeswar", region: "Nashik",
    total: 26.75, paid: 26.75, done: 26.75, pending: 0,
    deposits: 231023, farmers: 11, health: "on-track",
    deployed: [],
    pipeline: [],
    sheds: "Shankar Palkhede (18 cap)",
    alerts: [
      "26.75ac COMPLETED — 100% done. First cluster to reach full completion.",
      "Hemraj Waghmare team freed up — moved to Vaygaon/Malegaon for non-pruning activities.",
      "Eknath Palkhede situation fully resolved. Farmer served.",
      "Rathi Farm 8ac completed despite plastic clips delay.",
    ],
  },
  {
    id: "anjaneri", name: "Talegaon Anjaneri", region: "Nashik",
    total: 30.25, paid: 30.25, done: 30.25, pending: 0,
    deposits: 0, farmers: 5, health: "on-track",
    deployed: [],
    pipeline: [],
    sheds: "On farmer's property",
    alerts: [
      "30.25ac COMPLETED — 100% done. Second cluster fully completed.",
      "All farmers served: Bhagirathibai, Anita Chavan, etc.",
      "Hemraj Waghmare team fully freed from this cluster.",
    ],
  },
  {
    id: "satana", name: "Satana (Tembhe/Waygaon)", region: "Satana",
    total: 40.97, paid: 40.97, done: 32.53, pending: 8.44,
    deposits: 210400, farmers: 8, health: "on-track",
    deployed: [
      { team: "Ramesh Pithe (split)", members: 22, type: "stationed", status: "working", farmer: "Nilesh Keda Chavan / Vikram Kapadnis", note: "Active since 13 Mar. Pruning + non-pruning. Vikram Kapadnis 2.23ac added 16 Mar. Non-pruning from 20th (Nilesh Keda Chavan)." },
    ],
    pipeline: [],
    sheds: "Satana shed ready",
    alerts: [
      "32.53ac completed (79%) — best completion rate of active clusters.",
      "Vikram Kapadnis (2.23ac) added 16 Mar — pruning needed.",
      "Non-pruning activities start 20 Mar onwards: Nilesh Keda Chavan, Bablu Wagh pasting.",
      "Bansidhar Pawar leaf removal activity requested — team needed for Vaygaon.",
    ],
  },
  {
    id: "yeola", name: "Yeola/Patoda", region: "Yeola",
    total: 24.99, paid: 24.99, done: 16.64, pending: 8.35,
    deposits: 98730, farmers: 15, health: "on-track",
    deployed: [
      { team: "Tulsiram Gaikwad", members: 18, type: "stationed", status: "working", farmer: "Patoda remaining plots", note: "Took day off 17 Mar (continuous work fatigue). Farm manager absent. Resumed 18 Mar. Uttam Bornare 4.25ac next." },
    ],
    pipeline: [],
    sheds: "Patoda fabricated shed (18 cap, ₹8K invested) — active",
    alerts: [
      "16.64ac completed (67%) — strong progress from 12.89ac on 13 Mar.",
      "Tulsiram took a day off 17 Mar — team fatigue after continuous work.",
      "Uttam Bornare 4.25ac upcoming.",
      "Krushna Sonawane cordon tying added retroactively — resolved.",
    ],
  },
  {
    id: "nanegaon", name: "Nanegaon", region: "Nashik/Sinner",
    total: 28, paid: 28, done: 11.75, pending: 16.25,
    deposits: 0, farmers: 8, health: "warning",
    deployed: [],
    pipeline: [
      { name: "Janardhan Bhoye (13)", eta: "20 Mar", conf: 80, note: "Bhoye to return from Pandhurli. Amit requesting team from tomorrow (17 Mar message)." },
    ],
    sheds: "Keshav Kale (20 cap) — temporary",
    alerts: [
      "11.75ac done (42%). No active team currently — Bhoye needed back.",
      "Amit Patil requesting team from 18 Mar for ~8-10ac work.",
      "Vilas Shinde 3ac new booking.",
      "Growth cluster — needs regular team rotation.",
    ],
  },
  {
    id: "malegaon", name: "Malegaon (Rawalgaon + Vaygaon)", region: "Malegaon",
    total: 37.5, paid: 37.5, done: 12.5, pending: 25,
    deposits: 82500, farmers: 2, health: "warning",
    deployed: [
      { team: "Hemraj Waghmare", members: 14, type: "stationed", status: "working", farmer: "Bansidhar Pawar (Vaygaon)", note: "Freed from P.Garudeswar + Anjaneri. Now at Vaygaon. Bansidhar needs leaf removal + stem tying. 12.5ac stem tying done." },
    ],
    pipeline: [],
    sheds: "Vaygaon shed, Rawalgaon shed (Ramdas Patil — date TBD)",
    alerts: [
      "Rawalgaon 25ac — COMPLETED (Ramdas Waman Patil). Stem tying 10ac done.",
      "Vaygaon Bansidhar Pawar: 12.5ac total. Leaf removal scissors activity needed — Sairaj following up 16 Mar.",
      "Hemraj Waghmare most reliable team — now deployed for non-pruning work.",
      "Rawalgaon 25ac pruning to be confirmed date from Ramdas (22 Mar target).",
    ],
  },
  {
    id: "niphad", name: "Niphad", region: "Niphad",
    total: 3.95, paid: 3.95, done: 0, pending: 3.95,
    deposits: 0, farmers: 2, health: "critical",
    deployed: [],
    pipeline: [],
    sheds: "None identified",
    alerts: [
      "3.95ac with ZERO team and ZERO progress. Rohan Mogal (Kothure) calling continuously since 10 Mar.",
      "Sarthak flagged on 15 Mar — no team arranged still.",
      "Small cluster — hard to justify dedicated team. Need overflow from nearby cluster.",
      "17th March onwards per discussion — still no deployment.",
    ],
  },
  {
    id: "dondgav", name: "Dondgavhanwadi/Goharthan", region: "Chandwad",
    total: 17.09, paid: 17.09, done: 6.34, pending: 10.75,
    deposits: 0, farmers: 4, health: "warning",
    deployed: [
      { team: "Vilas Pawar (up-down)", members: 7, type: "up-down", status: "working-late", farmer: "Various", note: "Intermittent up-down. Chaure team. Unreliable but active some days." },
    ],
    pipeline: [],
    sheds: "None — up-down teams only",
    alerts: [
      "6.34ac done at Goharthan. Dondgavhanwadi (3.5ac) and remaining Goharthan pending.",
      "Vilas Pawar team intermittently available — same reliability issues.",
      "Low priority — overflow from Vadner teams will eventually cover.",
    ],
  },
  {
    id: "puri", name: "Puri", region: "Chandwad",
    total: 11, paid: 11, done: 11, pending: 0,
    deposits: 56540, farmers: 1, health: "on-track",
    deployed: [],
    pipeline: [],
    sheds: "N/A",
    alerts: [
      "11ac COMPLETED — AVEE Broiler fully served.",
      "Done by Ramesh Pithe early in cycle.",
    ],
  },
];

const TEAMS = [
  { name: "Yashwant Shevare", members: 30, tier: 1, loc: "Vadner Bhairav", status: "working", done: 18, days: 4, rel: 90, pay: "OK", app: false,
    payNote: "₹3500/ac. Permanent team.", risk: "Biggest team — arrived 15 Mar. Salukhe shed unavailable (harvesters). Temporary accommodation arranged. Has extended team in Dindori (not on tender yet)." },
  { name: "Hemraj Waghmare", members: 14, tier: 1, loc: "Vaygaon (Malegaon)", status: "working", done: 68.75, days: 24, rel: 95, pay: "OK", app: true,
    payNote: "₹20K Holi advance paid. Most reliable team.", risk: "P.Garudeswar + Anjaneri COMPLETED. Now on non-pruning at Vaygaon. Freed up = huge win." },
  { name: "Janardhan Bhoye", members: 23, tier: 1, loc: "Pandhurli (Sinner)", status: "working", done: 36, days: 24, rel: 92, pay: "OK", app: true,
    payNote: "₹15K/week resolved.", risk: "12.7ac done at Pandhurli. Cordon tying started. Amit wants him back at Nanegaon. Competing demands." },
  { name: "Tulsiram Gaikwad", members: 18, tier: 1, loc: "Patoda (Yeola)", status: "working", done: 30, days: 24, rel: 85, pay: "OK", app: true,
    payNote: "No issues.", risk: "Took day off 17 Mar — continuous work fatigue. Farm manager absent. Resumed 18 Mar. Patoda nearly done." },
  { name: "Digambar Pawar", members: 22, tier: 1, loc: "Vadner Bhairav", status: "working", done: 20, days: 6, rel: 88, pay: "OK", app: true,
    payNote: "First-time team from Surgana. Good work ethic.", risk: "Consistently working since 13 Mar arrival. Tata Strive team impressed. Geo-tagged photos shared 18 Mar." },
  { name: "Ramesh Pithe", members: 22, tier: 2, loc: "Satana + Khadak Ozar (split)", status: "split", done: 49, days: 22, rel: 72, pay: "OK", app: true,
    payNote: "Acre-based weekly payment resolved.", risk: "Split: main at Satana + squad at KO. Non-pruning starts 20 Mar. Overcommitted across 2 clusters." },
  { name: "Pushparaj Kadali", members: 15, tier: 2, loc: "Mohadi (Dindori)", status: "working", done: 12, days: 8, rel: 70, pay: "OK", app: true,
    payNote: "Rate settled.", risk: "Moved MRDBS→Mohadi 18 Mar. Farmer Dhananjay Jadhav wasn't at plot when team arrived. Communication gap." },
  { name: "Khandu Kamdi", members: 10, tier: 2, loc: "Kolhewadi (Sinner)", status: "working", done: 7, days: 7, rel: 75, pay: "OK", app: false,
    payNote: "₹20K + ₹500 chatni + ₹500 olandi bandhani.", risk: "Moved Chikani→Kolhewadi 18 Mar. Kolhewadi plots were wet, now dry. Tushar Dighe 19.5ac ahead." },
  { name: "Umesh Khambait", members: 9, tier: 2, loc: "Jawalke Vani (Dindori)", status: "working", done: 2, days: 2, rel: 70, pay: "OK", app: false,
    payNote: "₹20,200 total rate. ₹5K advance paid.", risk: "NEW team from 17 Mar. 3 more workers may join. Finalized by Roshan. First assignment." },
  { name: "Hemraj Kadali", members: 18, tier: 3, loc: "Vadner Bhairav (up-down)", status: "working-late", done: 6, days: 8, rel: 35, pay: "TBD", app: false,
    payNote: "Arranged by Rohan. Transport-dependent.", risk: "Missed 17 Mar — driver had accident, no alternate vehicle. Only 2 vehicles in village, same owner. Very unreliable." },
];

const FAILED_PIPELINE = [
  { name: "Vitthal Pawar (14)", date: "14→18 Mar", reason: "Didn't show for Vadner 14th. Didn't show for Mohadi 18th. Personal reasons. Pattern of no-shows.", lesson: "Up-down team with transport dependency = unreliable. Must have stationed alternatives." },
  { name: "Dhanraj Choudhary (18)", date: "14 Mar", reason: "Was supposed to come to Dindori. Didn't come. No backup deployed.", lesson: "Pipeline teams confirming ≠ arriving. Always have backup plan." },
  { name: "Pundalik Raut (10)", date: "14 Mar", reason: "Took work elsewhere on the same day.", lesson: "Competing opportunities pull teams away at last minute." },
  { name: "Vinod Wagh (15)", date: "17→20 Mar", reason: "Postponed arrival from 17th to 20th. Agent-mediated team.", lesson: "Agent-sourced teams have extra layer of unreliability." },
  { name: "Namdev Kharpade (16)", date: "10 Mar", reason: "Team didn't trust payment terms despite Mukkadam agreeing.", lesson: "TRUST > PRICE. Teams need to see others getting paid." },
  { name: "Mohan Gotarne (14)", date: "8→11 Mar", reason: "Funeral delay. Now unreachable — house locked, phone off.", lesson: "Single-point dependency on Mukkadam. Need alternate contact." },
  { name: "Uttam Bhadaye (16)", date: "5 Mar", reason: "Team went for bamboo/mango work at ₹700-800/day.", lesson: "Alternative income is the competition, not other platforms." },
  { name: "Dharma Dhikale (14)", date: "10→13 Mar", reason: "Confirmed 11th, no-show. Shifted to 13th. Still no show.", lesson: "MRDBS account partially recovered by Pushparaj instead." },
  { name: "Vilas Pawar (7)", date: "13 Mar→ongoing", reason: "Harvesting at Dindori. Shows up intermittently.", lesson: "Up-down teams with local work = will always prioritize their own harvesting." },
  { name: "Sunanda Kharate (16)", date: "5 Mar", reason: "Team members simply not interested in working.", lesson: "Mukkadam commitment ≠ team commitment. Verify with 2-3 members." },
];

const PAYMENT_ESCALATIONS = [
  { team: "Janardhan Bhoye", ask: "₹15K/week (was ₹10K)", math: "₹10K ÷ 22 ÷ 7d = ₹65/person/day for food", impact: "Sinner stable. Resolved.", rec: "DONE", urgency: "resolved", costDelta: "₹5K/week" },
  { team: "Ramesh Pithe", ask: "Acre-based weekly, not new rules", math: "Sat idle full day (8 Mar). Ultimatum resolved.", impact: "KO + Satana stable.", rec: "DONE", urgency: "resolved", costDelta: "₹0 — policy consistency" },
  { team: "Umesh Khambait", ask: "₹20,200 total rate + ₹5K advance", math: "₹3400 chatani + ₹1000 olandi + extras. Above standard.", impact: "New permanent team for Jawalke Vani.", rec: "ACCEPTED", urgency: "done", costDelta: "+₹700 vs baseline" },
  { team: "Hemraj Waghmare", ask: "₹20K advance for Holi", math: "One-time. Team has 95% reliability.", impact: "Goodwill with best team", rec: "PAID", urgency: "done", costDelta: "₹20K one-time" },
  { team: "Khandu Kamdi", ask: "₹20K + ₹500 Chatni + ₹500 Olandi", math: "Above standard ₹19.5K rate", impact: "Permanent team in Sinner", rec: "ACCEPTED", urgency: "done", costDelta: "+₹1K/tender" },
  { team: "Yashwant Shevare", ask: "₹3,500/ac pruning", math: "30 PAX. Standard rate.", impact: "Vadner 152ac. Biggest incoming.", rec: "ACCEPTED", urgency: "done", costDelta: "Standard" },
];

const FARMER_FRUSTRATION = [
  { farmer: "Vijay Kalamkar", cluster: "Dindori (Mohadi)", acres: 17.75, status: "FRUSTRATED", detail: "Team scheduled 18 Mar didn't show (Vitthal Pawar no-show). Farmer sharing angry messages about service. ₹2.62L tender.", daysOverdue: 1, revenue: 262000 },
  { farmer: "Anil Kad", cluster: "Dindori (Vani)", acres: 15, status: "FRUSTRATED", detail: "Cordon tying STILL UNRESOLVED since 13 Mar. Rohan escalating 18 Mar. Ashok Patil also calling. Need female team.", daysOverdue: 6, revenue: 0 },
  { farmer: "Rohan Mogal", cluster: "Niphad (Kothure)", acres: 1.95, status: "ABANDONED", detail: "Calling continuously since 10 Mar. Sarthak flagged 15 Mar. ZERO team sent. 9 days overdue.", daysOverdue: 9, revenue: 0 },
  { farmer: "Jaywant Shinde", cluster: "Vadner (Dewargaon)", acres: 8.75, status: "PRIORITY", detail: "FIRST-EVER customer. Wife passed away 5-6 days ago. Urgently needs 5ac pruning in 3-4 days. Azhaan: 'We owe it to him.'", daysOverdue: 0, revenue: 157500 },
  { farmer: "Bansidhar Pawar", cluster: "Malegaon (Vaygaon)", acres: 12.5, status: "WAITING", detail: "Leaf removal scissors activity needed. Sairaj following up since 16 Mar. Hemraj Waghmare now at Vaygaon.", daysOverdue: 2, revenue: 62500 },
  { farmer: "Vadner remaining group", cluster: "Vadner Bhairav", acres: 120, status: "QUEUED", detail: "152ac pending. 52 laborers (Digambar + Shevare). ~8-10ac/day. Need 15+ more weeks at current pace without reinforcement.", daysOverdue: 0, revenue: 2160000 },
  { farmer: "MRDBS/Avinash", cluster: "Dindori", acres: 14, status: "PARTIALLY SERVED", detail: "6.25ac done (was 0 on 13 Mar). Pushparaj Kadali deployed. Relationship partially recovered. 7.75ac remaining.", daysOverdue: 6, revenue: 0 },
  { farmer: "Dhananjay Jadhav", cluster: "Dindori (Mohadi)", acres: 1.5, status: "CONFUSION", detail: "Team arrived 18 Mar but farmer wasn't at plot. Miscommunication on timing. Vivek resolved same day. Work started.", daysOverdue: 0, revenue: 5400 },
  { farmer: "Eknath Palkhede", cluster: "P.Garudeswar", acres: 4.25, status: "RESOLVED", detail: "Team reached 11 Mar. All work completed. P.Garudeswar 100% done.", daysOverdue: 0, revenue: 14550 },
  { farmer: "Abhijit Ahire", cluster: "Satana (Tembhe)", acres: 2.44, status: "RESOLVED", detail: "Pithe arrived 13 Mar. Crimson tender saved. Work completed.", daysOverdue: 0, revenue: 43920 },
];

const UNCOLLECTED_DEPOSITS = [
  { id: 904, farmer: "Balu Popat", poc: "Amit", amount: 100000 },
  { id: 890, farmer: "Vaibhav Shinde", poc: "Amit", amount: 36600 },
  { id: 883, farmer: "Abhiraj Malunkar", poc: "Amit", amount: 80300 },
  { id: 848, farmer: "Rahul Dhatrak", poc: "Amit", amount: 37400 },
  { id: 847, farmer: "Whitman Dargode", poc: "Amit", amount: 42125 },
  { id: 840, farmer: "Deeper Dhatrak", poc: "Amit", amount: 88875 },
  { id: 839, farmer: "Mahesh Dargode", poc: "Amit", amount: 36500 },
  { id: 703, farmer: "Dnyaneshwar Varpe", poc: "Amit", amount: 64650 },
  { id: 800, farmer: "Yogish Bornare", poc: "Sairaj", amount: 49980 },
  { id: 799, farmer: "Dilip Sonamwane", poc: "Sairaj", amount: 31875 },
  { id: 416, farmer: "Alka Arjun Wagh", poc: "Sairaj", amount: 34545 },
  { id: 842, farmer: "Valuba Rachael", poc: "Sarthak", amount: 99000 },
];

const DATA_QUALITY = [
  { issue: "Bansidhar Pawar acreage: system 2ac, actual 12.5ac", impact: "10.5ac invisible to allocation — Sairaj flagged 2 Mar", owner: "Sarthak" },
  { issue: "Sale app loading issues — 16 Mar (resolved same day)", impact: "Bookings blocked for hours. Payment system down briefly.", owner: "Hemanthh" },
  { issue: "Activity sequence not automated in app", impact: "Sairaj: 'farmers questioning activity order'. Manual correction needed.", owner: "Gourav/Hemanthh" },
  { issue: "Farmer not informed before team arrival", impact: "Dhananjay Jadhav not at plot when Pushparaj arrived 18 Mar. Amit: 'Inform 1 day in advance.'", owner: "Vivek/Demand team" },
  { issue: "Hemraj Kadali transport single-point failure", impact: "Only 2 vehicles in village, same owner. Missed 17 Mar entirely.", owner: "Roshan" },
  { issue: "Vitthal Pawar status ambiguous", impact: "Scheduled for Vadner 14th AND Mohadi 18th — didn't show either. Is he still working with us?", owner: "Animesh/Vivek" },
  { issue: "Facebook leads ROI tracking requested by Azhaan", impact: "150 CNC leads. Komal shared report 16 Mar. Need conversion tracking.", owner: "Komal" },
  { issue: "WhatsApp → Slack migration started 19 Mar", impact: "Field ops (Love, Vicky, Ajinkya) moving to Slack. Transition period may cause gaps.", owner: "Azhaan/Animesh" },
];

const PIPELINE_FUNNEL = [
  { stage: "Completed", acres: 280.56, color: "#16a34a" },
  { stage: "In Progress", acres: 12.05, color: "#2563eb" },
  { stage: "Yet to Start", acres: 205.11, color: "#7c3aed" },
  { stage: "Pipeline Leads", acres: 1401, color: "#d97706" },
];

const WEEKLY_BOOKINGS = [
  { week: "Jan W5", acres: 2.92 },
  { week: "Feb W1", acres: 13.51 }, { week: "Feb W2", acres: 4.1 },
  { week: "Feb W3", acres: 36.73 }, { week: "Feb W4", acres: 39.09 },
  { week: "Mar W1", acres: 358.4 }, { week: "Mar W2", acres: 199.63 },
  { week: "Mar W3", acres: 76.96 }, { week: "Mar W4", acres: 23.45 },
  { week: "Mar W5", acres: 7.89 },
];

const TEAM_SCHEDULE = [
  { team: "Hemraj Waghmare (14)", t: "T1", d: [[5,12,"P.Garudeswar"],[11,16,"Anjaneri"],[17,30,"Vaygaon"]] },
  { team: "Janardhan Bhoye (23)", t: "T1", d: [[5,6,"Khadak Ozar"],[8,11,"Nanegaon"],[12,25,"Pandhurli"],[26,30,"Nanegaon?"]] },
  { team: "Tulsiram Gaikwad (18)", t: "T1", d: [[8,8,"Talegaon Wani"],[9,14,"Vadner"],[15,30,"Patoda"]] },
  { team: "Digambar Pawar (22)", t: "T1", d: [[13,30,"Vadner Bhairav"]] },
  { team: "Yashwant Shevare (30)", t: "T1", d: [[15,30,"Vadner Bhairav"]] },
  { team: "Ramesh Pithe (22)", t: "T2", d: [[10,12,"Khadak Ozar"],[13,16,"Satana"],[17,20,"KO + Satana"],[21,30,"Satana non-prune"]] },
  { team: "Pushparaj Kadali (15)", t: "T2", d: [[12,13,"Vani"],[14,17,"MRDBS"],[18,25,"Mohadi"]] },
  { team: "Khandu Kamdi (10)", t: "T2", d: [[13,17,"Chikani"],[18,30,"Kolhewadi"]] },
  { team: "Umesh Khambait (9)", t: "New", d: [[17,30,"Jawalke Vani"]] },
  { team: "Hemraj Kadali (18)", t: "T3", d: [[11,16,"Vadner"],[17,17,"OFF-driver"],[18,30,"Vadner?"]] },
  { team: "Vinod Wagh (15)", t: "New", d: [[20,30,"TBD"]] },
  { team: "Pandurang Deshmukh", t: "New", d: [[20,30,"KO / Dindori?"]] },
];

const WEEK_PLAN = [
  {
    day: "THU 19 MAR (TODAY)", label: "Gudi Padwa — Allocate + Decide", urgency: "critical",
    actions: [
      { priority: "P0", action: "Jaywant Shinde (Dewargaon) 5ac — allocate team today", owner: "Animesh/Vivek", why: "First-ever customer. Wife passed away. Azhaan directive. Check Vitthal Pawar or redirect an up-down team.", deadline: "By noon" },
      { priority: "P0", action: "Confirm Pushparaj working at Vijay Kalamkar's plot (Mohadi)", owner: "Vivek/Amit", why: "₹2.62L tender. Farmer furious after 18 Mar no-show. Call Kalamkar with concrete update.", deadline: "Morning call" },
      { priority: "P0", action: "Anil Kad cordon tying — source female team or new team NOW", owner: "Rohan/Roshan", why: "6 days overdue. Rohan escalated 18 Mar. Two contacts shared by Vivek. Negotiate rates.", deadline: "By noon" },
      { priority: "P1", action: "Vitthal Pawar: make a decision — station permanently or release", owner: "Animesh", why: "2 no-shows. Ghost team consuming planning bandwidth. Clear answer needed.", deadline: "By evening" },
      { priority: "P1", action: "Confirm Hemraj Kadali transport fix or station the team", owner: "Pradip/Vivek", why: "Missed 17 Mar. Single vehicle dependency. Find alternate or negotiate stationing.", deadline: "By evening" },
    ],
  },
  {
    day: "FRI 20 MAR", label: "Vinod Wagh Arrival + Non-Pruning Kickoff", urgency: "critical",
    actions: [
      { priority: "P0", action: "Vinod Wagh (15) arrival — confirm movement and deploy", owner: "Roshan/Animesh", why: "Postponed twice (17→20 Mar). Agent from Sakri. ₹17,500 rate. Not ready for paste-only. Deploy at Vadner (152ac pending) or Dindori.", deadline: "Morning check" },
      { priority: "P0", action: "Nanegaon ~8-10ac — deploy Bhoye rotation or Vinod Wagh", owner: "Vivek/Amit", why: "Amit requesting since 17 Mar. Vilas Shinde 3ac new. Bhoye ideal if Pandhurli allows rotation. Or redirect Vinod Wagh here.", deadline: "Confirm by noon" },
      { priority: "P0", action: "Nilwandi 6.8ac — deploy team per Ramdas ji commitment (20th date)", owner: "Vivek", why: "Farmer discussion confirmed 20 Mar. 0ac done. Who goes? Pushparaj after Mohadi? Umesh Khambait nearby?", deadline: "Morning" },
      { priority: "P1", action: "Satana non-pruning kickoff: Nilesh Keda Chavan + Bablu Wagh pasting", owner: "Vivek/Sairaj", why: "20th March target. Ramesh Pithe aligned. First non-pruning tender revenue. Confirm Pithe knows the rotation.", deadline: "Confirm" },
      { priority: "P1", action: "Facebook leads closure — 150 CNC leads (Komal report 16 Mar)", owner: "Amit/Sarthak/Sairaj", why: "Azhaan wants ROI. Booking velocity crashing (358→23ac/wk). Fastest path to new confirmed demand.", deadline: "Calls all day" },
    ],
  },
  {
    day: "SAT 21 MAR", label: "Velocity Check + Vaygaon + Kolhewadi", urgency: "high",
    actions: [
      { priority: "P0", action: "Week velocity review — 280ac on 19th, what's the number today?", owner: "Animesh/Vivek", why: "10 teams × ~2ac/day each = ~20ac/day target. Should be ~320ac by today. Measure reality vs plan.", deadline: "End of day" },
      { priority: "P0", action: "Bansidhar Pawar (Vaygaon) leaf removal — confirm Hemraj Waghmare progress", owner: "Vivek/Sairaj", why: "Sairaj following up since 16 Mar. 12.5ac. Leaf removal by scissors = new activity type. Farmer consistently chasing.", deadline: "Field check" },
      { priority: "P1", action: "Kolhewadi progress — Khandu Kamdi on Tushar Dighe 19.5ac", owner: "Vivek", why: "Moved 18 Mar from Chikani. Plots were wet earlier. Confirm pruning started and daily pace.", deadline: "Field check" },
      { priority: "P1", action: "Rawalgaon 25ac pruning — confirm date with Ramdas Waman Patil (22 Mar target)", owner: "Vivek", why: "Large single-farmer block. ₹20K deposit. If 22nd confirmed, deploy Waghmare after Vaygaon work.", deadline: "Call farmer" },
      { priority: "P1", action: "Vadner farmer queue — prepare next 7-day schedule for Digambar + Shevare", owner: "Sarthak/Vivek", why: "152ac pending with 52 laborers. Farmers need concrete dates. Amol Nikam, Balaji Patole, Valuba Gachale waiting.", deadline: "Prepare list" },
    ],
  },
  {
    day: "SUN 22 MAR", label: "Rawalgaon Deploy + Patoda Completion Push", urgency: "high",
    actions: [
      { priority: "P0", action: "Rawalgaon 25ac pruning start — deploy Hemraj Waghmare (14)", owner: "Vivek", why: "₹20K deposit. Ramdas Waman Patil. Waghmare is most reliable team (95%). Stem tying 10ac already done here.", deadline: "Morning deployment" },
      { priority: "P0", action: "Patoda completion check — Tulsiram Gaikwad remaining ~8ac", owner: "Vivek", why: "16.64ac done. Uttam Bornare 4.25ac next. If Patoda completes = 4th cluster at 100%. Frees Gaikwad for Vadner.", deadline: "Field check" },
      { priority: "P1", action: "Mohadi progress update — Pushparaj on Vijay Kalamkar 17.75ac", owner: "Vivek/Amit", why: "₹2.62L tender. Thomson+Crimson+Aara36 varieties. Farmer was furious — need visible progress report to him.", deadline: "Update farmer" },
      { priority: "P1", action: "Mukkadam app push — target 8/10 teams installed by weekend end", owner: "Love/Vicky/Ajinkya", why: "6/10 done. Umesh Khambait, Khandu Kamdi most accessible in field today. Structured data > WhatsApp.", deadline: "By EOD" },
      { priority: "P1", action: "MRDBS remaining 7.75ac — is Pushparaj returning after Mohadi or done?", owner: "Animesh/Vivek", why: "6.25ac done so far. Avinash Chopde relationship partially recovered. Don't let remaining work slip.", deadline: "Plan rotation" },
    ],
  },
  {
    day: "MON 23 MAR", label: "Deposit Sprint + Dindori Rotation", urgency: "high",
    actions: [
      { priority: "P0", action: "Deposit collection sprint — 32 unpaid bookings, ₹7.01L outstanding", owner: "Rohan/Sales team", why: "Amit alone has ₹4.87L uncollected. 2+ weeks old. Phantom demand distorts allocation. Enforce: no allocation for ₹0 bookings >7 days.", deadline: "All week target" },
      { priority: "P0", action: "Dindori team rotation — Pushparaj finishing Mohadi, where next?", owner: "Animesh/Vivek", why: "76ac pending. Nilwandi 6.8ac, Sonjamb 1.55ac, MRDBS remaining 7.75ac all at 0%. Plan Pushparaj's next 5 assignments.", deadline: "By noon" },
      { priority: "P0", action: "Narayangaon booking conversion — turn Sairaj's 16 Mar scouting into deposits", owner: "Sairaj/Rohan", why: "150ac April pipeline. First day experience report shared. Convert now before farmers cool off. Biggest booking opportunity.", deadline: "Calls all day" },
      { priority: "P1", action: "Sinner: Vadgaon Landga remaining 2.25ac + Chikani harvesting resume date", owner: "Vivek", why: "Vadgaon 7.1 of 9.35ac done. Chikani harvesting paused pruning — when does it resume? Khandu at Kolhewadi now.", deadline: "Check" },
      { priority: "P1", action: "Sonjamb 1.55ac — farmer date was 19th, now 4 days overdue", owner: "Vivek/Amit", why: "Small acreage but trust eroding. Can Umesh Khambait (Jawalke Vani, nearby) cover after current assignment?", deadline: "Assign or inform" },
    ],
  },
  {
    day: "TUE 24 MAR", label: "Vadner Reassessment + Pipeline Prep", urgency: "high",
    actions: [
      { priority: "P0", action: "Vadner 152ac reassessment — realistic completion timeline with 70 laborers", owner: "Animesh/Sarthak", why: "Digambar(22)+Shevare(30)+Kadali(18)=70. At ~10ac/day = 15+ weeks. Need 2 more teams or reset farmer expectations honestly.", deadline: "Review" },
      { priority: "P0", action: "Niphad escalation — 14+ days, zero progress. Final decision.", owner: "Rohan/Animesh", why: "Rohan Mogal (Kothure 1.95ac) calling since 10 Mar. Either send overflow team THIS WEEK or transparently release farmer.", deadline: "Decision" },
      { priority: "P1", action: "Pre-call Chandwad pipeline farmers — Pachorkar, Vakte, Shinde groups (100ac, vis 25/03)", owner: "Sarthak", why: "Pipeline visibility date is tomorrow. Confirm which farmers actually ready to book + pay deposit before committing.", deadline: "Calls" },
      { priority: "P1", action: "Mid-week team productivity audit: 181 laborers on paper — how many working today?", owner: "Animesh", why: "Hemraj Kadali transport? Vitthal resolved? Pithe split effective? Vinod Wagh arrived? Count real vs paper capacity.", deadline: "Audit by EOD" },
      { priority: "P1", action: "Khadak Ozar: Pithe at 16.5ac of 39.68ac — when does this cluster complete?", owner: "Vivek", why: "23ac remaining. At Pithe's pace (split with Satana), could be 3-4 more weeks. Pandurang Deshmukh as reinforcement?", deadline: "Estimate" },
    ],
  },
  {
    day: "WED 25 MAR", label: "Pipeline Visibility Day — Chandwad + Niphad", urgency: "critical",
    actions: [
      { priority: "P0", action: "Chandwad 100ac pipeline — Pachorkar, Vakte, Shinde Groups booking day", owner: "Sarthak/Rohan", why: "Visibility date. If 50% converts = 50ac new confirmed bookings. Biggest demand opportunity in 2 weeks. But: do NOT book without team allocation plan.", deadline: "Book with team plan" },
      { priority: "P0", action: "Niphad 60ac pipeline — Sanjay Patil 35ac, Kushare Group, Pimpri Sayyad", owner: "Sarthak/Rohan", why: "Visibility date. Kothure 1.95ac already 14+ days overdue. Do not repeat the mistake — only book if team is visible.", deadline: "Book only with team" },
      { priority: "P0", action: "Booking velocity check — did Facebook leads + Narayangaon outreach arrest the decline?", owner: "Rohan/Gourav", why: "W4: 23ac. W5: 8ac. If trend holds, demand pipeline is dying even as supply grows. Honest assessment needed.", deadline: "By evening" },
      { priority: "P1", action: "Sinner completion forecast — Kolhewadi 19.5ac + Bhojapur 6.7ac (April) remaining", owner: "Vivek", why: "36ac done of 103ac. Bhoye at Pandhurli, Kamdi at Kolhewadi. When does Sinner hit 80%? Target date.", deadline: "Forecast" },
      { priority: "P1", action: "Team fatigue check — Gaikwad took day off 17th, Pithe split across 2 clusters", owner: "Animesh/Vivek", why: "Continuous work without breaks = reliability drops. Proactively schedule rest days before teams ghost.", deadline: "Review" },
    ],
  },
  {
    day: "NEXT 7 DAYS", label: "Continuous Priorities (19-25 Mar)", urgency: "ongoing",
    actions: [
      { priority: "P0", action: "TRACK: % farmers who received team on scheduled date — target 65%", owner: "Anurag/Vivek", why: "Currently ~55% (up from 45%). Every point builds trust. Measure daily across all clusters. Report in Slack.", deadline: "Daily" },
      { priority: "P0", action: "Arrest booking velocity decline — 358ac→23ac/wk over 4 weeks", owner: "Rohan/Sales", why: "Supply growing but demand drying up. Push: 150 Facebook leads, Narayangaon deposits, Krushikumbh contacts. Consider April pricing.", deadline: "Active" },
      { priority: "P0", action: "No new bookings in teamless clusters without Animesh approval", owner: "Rohan/Sales", why: "Every booking in empty cluster = future broken promise. Niphad (9 days, 0 progress) is the cautionary tale.", deadline: "Policy" },
      { priority: "P1", action: "Non-pruning revenue: pasting, stem tying, leaf removal starting 20 Mar", owner: "Vivek/Sairaj", why: "Bablu Wagh, Bansidhar Pawar, Nilesh Chavan, Alka Wagh. Higher margins, lower labor intensity. Female teams viable.", deadline: "Active" },
      { priority: "P1", action: "Book tender-without-pruning at tender rates for post-pruning activities", owner: "Sales team", why: "Azhaan approved. Skip pruning = more time to find team. Expands addressable market without needing more pruning teams.", deadline: "Active" },
      { priority: "P1", action: "September pruning: start early deposit conversations with top 20 farmers", owner: "Rohan/Azhaan", why: "Lock farmer loyalty now. Avoid repeating the March scramble. Early bookings = guaranteed demand + planning time.", deadline: "Start" },
    ],
  },
];

const TABS = [
  { id: "command", label: "Command", badge: true },
  { id: "dispatch", label: "Dispatch" },
  { id: "teams", label: "Teams" },
  { id: "clusters", label: "Clusters" },
  { id: "business", label: "Business" },
  { id: "strategy", label: "Strategy" },
];

const fmt = (n) => n >= 100000 ? `₹${(n/100000).toFixed(1)}L` : n >= 1000 ? `₹${(n/1000).toFixed(0)}K` : `₹${n}`;

const Pill = ({ children, color = "#57534e", bg = "#f5f5f4" }) => (
  <span style={{ display: "inline-block", padding: "2px 9px", borderRadius: 12, fontSize: 10, fontWeight: 700, color, backgroundColor: bg, letterSpacing: 0.3, whiteSpace: "nowrap" }}>{children}</span>
);

const Section = ({ title, sub, children, urgent }) => (
  <div style={{ marginBottom: 22 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: urgent ? "#991b1b" : "#1c1917", letterSpacing: 0.3 }}>{title}</div>
      {sub && <div style={{ fontSize: 11, color: "#a8a29e" }}>{sub}</div>}
      {urgent && <Pill color="#991b1b" bg="#fee2e2">ACTION NEEDED</Pill>}
    </div>
    {children}
  </div>
);

const Card = ({ children, border = "#e7e5e4", bg = "#fff", style: s = {} }) => (
  <div style={{ backgroundColor: bg, border: `1px solid ${border}`, borderRadius: 10, padding: "14px 16px", ...s }}>{children}</div>
);

const KPI = ({ label, value, sub, color = "#1c1917", alert }) => (
  <div style={{ padding: "14px 16px", backgroundColor: alert ? "#fef2f2" : "#fff", borderRadius: 10, border: `1px solid ${alert ? "#fecaca" : "#e7e5e4"}` }}>
    <div style={{ fontSize: 9, fontWeight: 700, color: "#a8a29e", textTransform: "uppercase", letterSpacing: 1 }}>{label}</div>
    <div style={{ fontSize: 22, fontWeight: 700, color, fontFamily: "'IBM Plex Mono', monospace", marginTop: 4, lineHeight: 1 }}>{value}</div>
    {sub && <div style={{ fontSize: 10, color: "#a8a29e", marginTop: 5 }}>{sub}</div>}
  </div>
);

const hc = { "on-track": "#16a34a", warning: "#d97706", critical: "#dc2626" };
const hbg = { "on-track": "#dcfce7", warning: "#fef3c7", critical: "#fee2e2" };
const sc = { working: "#16a34a", split: "#2563eb", "working-late": "#d97706", idle: "#dc2626", "in-transit": "#7c3aed", arriving: "#06b6d4" };

const CTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ backgroundColor: "#1c1917", padding: "10px 14px", borderRadius: 8, boxShadow: "0 8px 32px rgba(0,0,0,0.24)" }}>
      <div style={{ fontSize: 11, color: "#a8a29e", marginBottom: 4, fontWeight: 600 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 12, color: p.color || "#e2e8f0" }}>
          {p.name}: {typeof p.value === "number" ? (p.value > 500 ? fmt(p.value) : p.value.toLocaleString()) : p.value}
        </div>
      ))}
    </div>
  );
};

export default function AgroIntelUnified() {
  const [tab, setTab] = useState("command");
  const [xCluster, setXCluster] = useState(null);
  const [xWeek, setXWeek] = useState(0);
  const [selCluster, setSelCluster] = useState(null);

  const totalLabor = TEAMS.reduce((s, t) => s + t.members, 0);
  const critCount = CLUSTERS.filter(c => c.health === "critical").length;
  const totalPending = CLUSTERS.reduce((s, c) => s + c.pending, 0);
  const frustratedCount = FARMER_FRUSTRATION.filter(f => ["BRAND DAMAGE", "CHURN RISK", "FRUSTRATED", "DEADLINE PASSED", "OVERDUE", "UNKNOWN", "ABANDONED"].includes(f.status)).length;
  const atRiskRevenue = FARMER_FRUSTRATION.reduce((s, f) => s + f.revenue, 0);
  const ganttDays = Array.from({ length: 22 }, (_, i) => i + 9);

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#fafaf9", fontFamily: "'Instrument Sans', -apple-system, BlinkMacSystemFont, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; } ::-webkit-scrollbar-thumb { background: #d6d3d1; border-radius: 4px; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
      `}</style>

      {/* HEADER */}
      <div style={{ backgroundColor: "#1c1917", padding: "16px 28px 0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: 3, color: "#78716c", textTransform: "uppercase" }}>AgroIntel</div>
            <h1 style={{ fontSize: 22, fontWeight: 400, color: "#fafaf9", fontFamily: "'Instrument Serif', Georgia, serif", marginTop: 2 }}>
              Unified Command Center
            </h1>
          </div>
          <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
            <div style={{ display: "flex", gap: 16, fontFamily: "'IBM Plex Mono', monospace", fontSize: 11 }}>
              <span style={{ color: "#86efac" }}>{TEAMS.filter(t => t.status === "working" || t.status === "split").length} working</span>
              <span style={{ color: "#fde68a" }}>{TEAMS.filter(t => t.status === "arriving").length || 0} transit</span>
              <span style={{ color: "#fca5a5", animation: critCount > 0 ? "pulse 2s infinite" : "none" }}>{critCount} critical</span>
            </div>
            <div style={{ textAlign: "right", fontSize: 11, color: "#78716c" }}>
              <div style={{ color: "#a8a29e" }}>19 Mar 2026 · <span style={{ color: "#d6d3d1" }}>10 AM</span></div>
            </div>
          </div>
        </div>

        {/* Vitals strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1, margin: "0 -28px", backgroundColor: "#292524" }}>
          {[
            { l: "DEPLOYED", v: totalLabor, s: "laborers", c: "#60a5fa" },
            { l: "CRITICAL", v: critCount, s: `of ${CLUSTERS.length}`, c: "#f87171" },
            { l: "PENDING", v: `${totalPending.toFixed(0)}ac`, s: "yet to start", c: "#fbbf24" },
            { l: "BACKLOG", v: `${(totalPending / 120).toFixed(1)}wk`, s: "at 120ac/wk", c: "#f87171" },
            { l: "AT-RISK", v: frustratedCount, s: "farmers", c: "#f87171" },
            { l: "₹ AT RISK", v: fmt(atRiskRevenue), s: "revenue", c: "#fbbf24" },
            { l: "SHOW-UP", v: "~55%", s: "10 of 18 failed", c: "#d97706" },
          ].map((v, i) => (
            <div key={i} style={{ padding: "8px 12px", backgroundColor: "#1c1917" }}>
              <div style={{ fontSize: 8, fontWeight: 800, letterSpacing: 1.5, color: "#57534e" }}>{v.l}</div>
              <div style={{ fontSize: 17, fontWeight: 800, color: v.c, fontFamily: "'IBM Plex Mono', monospace", marginTop: 1 }}>{v.v}</div>
              <div style={{ fontSize: 9, color: "#57534e" }}>{v.s}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 0, margin: "0 -28px", padding: "0 28px", borderTop: "1px solid #292524" }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => { setTab(t.id); setSelCluster(null); setXCluster(null); }} style={{
              padding: "10px 18px", fontSize: 12, fontWeight: 600, cursor: "pointer", border: "none",
              color: tab === t.id ? "#fafaf9" : "#78716c", backgroundColor: "transparent",
              borderBottom: tab === t.id ? "2px solid #f5f5f4" : "2px solid transparent",
              fontFamily: "'Instrument Sans', sans-serif", transition: "all 0.15s",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              {t.label}
              {t.badge && critCount > 0 && <span style={{ fontSize: 9, backgroundColor: "#dc2626", color: "#fff", borderRadius: 8, padding: "1px 6px", fontWeight: 800 }}>{critCount}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* CONTENT */}
      <div style={{ padding: "20px 28px", maxWidth: 1360, margin: "0 auto" }}>

        {/* COMMAND TAB */}
        {tab === "command" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>
            <Card bg="#fef2f2" border="#fecaca" style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 10, fontWeight: 800, color: "#991b1b", letterSpacing: 1.5, marginBottom: 8, textTransform: "uppercase" }}>Critical — Requires Action Today</div>
              {[
                { text: "JAYWANT SHINDE (Dewargaon) 5ac — first-ever customer. Wife passed away. Azhaan: 'We owe it to him.' Allocate team today — even temporary redirect.", tag: "P0" },
                { text: "VIJAY KALAMKAR (Mohadi) ₹2.62L tender — team no-show 18 Mar. Confirm Pushparaj is working on his plot and call farmer with update.", tag: "P0" },
                { text: "ANIL KAD cordon tying 6 DAYS OVERDUE — Rohan escalated 18 Mar. Ashok Patil also calling. Identify female team or new permanent today or lose this farmer.", tag: "P0" },
                { text: "VITTHAL PAWAR — 2 consecutive no-shows (14th, 18th). Make a call: station him permanently or release. Ghost teams waste planning capacity.", tag: "DECIDE" },
                { text: "BOOKING VELOCITY DECLINING — 358ac (W1) → 77ac (W3) → 23ac (W4). New bookings slowing. Push Facebook leads closure + Narayangaon follow-ups.", tag: "DEMAND" },
                { text: "NIPHAD (Rohan Mogal) — 9 DAYS, zero team, zero progress. Either assign overflow team or transparently tell farmer we can't serve him.", tag: "FARMER" },
              ].map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: "5px 0", borderBottom: i < 5 ? "1px solid #fecaca" : "none" }}>
                  <Pill color={a.tag === "P0" ? "#991b1b" : a.tag === "DECIDE" ? "#7c3aed" : a.tag === "DEMAND" ? "#1e40af" : a.tag === "FARMER" ? "#c2410c" : "#1e40af"} bg={a.tag === "P0" ? "#fee2e2" : a.tag === "DECIDE" ? "#ede9fe" : a.tag === "DEMAND" ? "#dbeafe" : a.tag === "FARMER" ? "#ffedd5" : "#dbeafe"}>{a.tag}</Pill>
                  <div style={{ fontSize: 11, color: "#44403c", lineHeight: 1.5, flex: 1 }}>{a.text}</div>
                </div>
              ))}
            </Card>

            <Section title="Farmer Frustration Tracker" sub={`${frustratedCount} critical · ${fmt(atRiskRevenue)} at risk`} urgent>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {FARMER_FRUSTRATION.map((f, i) => {
                  const fc = { "CALMING": "#16a34a", "FRUSTRATED": "#dc2626", "DEADLINE PASSED": "#dc2626", "DELAYED": "#d97706", "ANXIOUS": "#d97706", "WAITING": "#d97706", "STRATEGIC": "#2563eb", "OVERDUE": "#ea580c", "COMPLAINED": "#ea580c", "SAVED": "#16a34a", "UNKNOWN": "#dc2626", "RESOLVED": "#16a34a", "PARTIALLY SERVED": "#d97706", "QUEUED": "#2563eb", "PRIORITY": "#dc2626", "ABANDONED": "#dc2626", "CONFUSION": "#d97706" };
                  const isCrit = ["FRUSTRATED", "DEADLINE PASSED", "OVERDUE", "UNKNOWN", "ABANDONED", "PRIORITY"].includes(f.status);
                  return (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "150px 110px 100px 1fr", gap: 8, padding: "8px 12px", backgroundColor: isCrit ? "#fef2f2" : "#fff", borderRadius: 8, border: `1px solid ${isCrit ? "#fecaca" : "#e7e5e4"}`, fontSize: 11, alignItems: "center", animation: `fadeUp 0.3s ease ${i * 0.03}s both` }}>
                      <div>
                        <div style={{ fontWeight: 700, color: "#1c1917" }}>{f.farmer}</div>
                        <div style={{ fontSize: 10, color: "#a8a29e" }}>{f.cluster} {f.acres > 0 ? `· ${f.acres}ac` : ""}</div>
                      </div>
                      <Pill color={fc[f.status] || "#57534e"} bg={(fc[f.status] || "#57534e") + "18"}>{f.status}</Pill>
                      <div style={{ fontSize: 10, color: "#78716c" }}>{f.daysOverdue > 0 ? `+${f.daysOverdue}d overdue` : ""} {f.revenue > 0 ? `· ${fmt(f.revenue)}` : ""}</div>
                      <div style={{ fontSize: 10, color: "#57534e" }}>{f.detail}</div>
                    </div>
                  );
                })}
              </div>
            </Section>

            <Section title="Cluster Status" sub="Click to expand">
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {CLUSTERS.sort((a, b) => ({ critical: 0, warning: 1, "on-track": 2 }[a.health] ?? 3) - ({ critical: 0, warning: 1, "on-track": 2 }[b.health] ?? 3)).map((c, i) => {
                  const open = xCluster === i;
                  const pct = c.total > 0 ? ((c.done / c.total) * 100).toFixed(0) : 0;
                  const lab = c.deployed.reduce((s, t) => s + t.members, 0);
                  return (
                    <div key={i} style={{ backgroundColor: "#fff", border: `1px solid ${c.health === "critical" ? "#fecaca" : c.health === "warning" ? "#fde68a" : "#e7e5e4"}`, borderRadius: 8, overflow: "hidden", animation: `fadeUp 0.3s ease ${i * 0.03}s both` }}>
                      <div onClick={() => setXCluster(open ? null : i)} style={{ padding: "10px 14px", cursor: "pointer", display: "grid", gridTemplateColumns: "200px 70px 110px 60px 1fr 24px", gap: 8, alignItems: "center" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: hc[c.health], flexShrink: 0 }} />
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: "#1c1917" }}>{c.name}</div>
                            <div style={{ fontSize: 10, color: "#a8a29e" }}>{c.region} · {c.farmers}f</div>
                          </div>
                        </div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: "#1c1917", fontFamily: "'IBM Plex Mono', monospace" }}>{c.total}<span style={{ fontSize: 10, color: "#a8a29e" }}>ac</span></div>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <div style={{ flex: 1, height: 4, backgroundColor: "#f5f5f4", borderRadius: 2 }}>
                              <div style={{ width: `${pct}%`, height: "100%", borderRadius: 2, backgroundColor: hc[c.health] }} />
                            </div>
                            <span style={{ fontSize: 10, fontWeight: 700, color: hc[c.health], fontFamily: "'IBM Plex Mono', monospace" }}>{pct}%</span>
                          </div>
                          <div style={{ fontSize: 9, color: "#a8a29e" }}>{c.done}✓ / {c.pending} left</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: lab === 0 ? "#dc2626" : "#1c1917", fontFamily: "'IBM Plex Mono', monospace" }}>{lab}</div>
                          <div style={{ fontSize: 9, color: "#a8a29e" }}>labor</div>
                        </div>
                        <div style={{ fontSize: 10, color: "#78716c" }}>
                          {c.deployed.length > 0 ? c.deployed.map(t => t.team).join(" · ") : <span style={{ color: "#dc2626", fontWeight: 700 }}>NO TEAM</span>}
                        </div>
                        <div style={{ fontSize: 11, color: "#a8a29e" }}>{open ? "▾" : "▸"}</div>
                      </div>
                      {open && (
                        <div style={{ padding: "0 14px 14px", borderTop: "1px solid #f5f5f4", animation: "fadeUp 0.2s ease" }}>
                          <div style={{ margin: "10px 0", padding: "8px 10px", backgroundColor: hbg[c.health], borderRadius: 6 }}>
                            {c.alerts.map((a, j) => <div key={j} style={{ fontSize: 11, color: hc[c.health], lineHeight: 1.5, padding: "2px 0" }}>→ {a}</div>)}
                          </div>
                          {c.deployed.length > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <div style={{ fontSize: 9, fontWeight: 800, color: "#a8a29e", letterSpacing: 1, marginBottom: 4, textTransform: "uppercase" }}>Deployed Teams</div>
                              {c.deployed.map((t, j) => (
                                <div key={j} style={{ display: "grid", gridTemplateColumns: "160px 100px 160px 1fr", gap: 6, padding: "5px 8px", backgroundColor: j % 2 ? "transparent" : "#fafaf9", borderRadius: 4, fontSize: 11, alignItems: "center" }}>
                                  <span style={{ fontWeight: 600, color: "#1c1917" }}>{t.team} ({t.members})</span>
                                  <span style={{ color: sc[t.status] || "#78716c" }}>● {t.status} · {t.type}</span>
                                  <span style={{ color: "#57534e" }}>{t.farmer}</span>
                                  <span style={{ color: "#a8a29e", fontSize: 10 }}>{t.note}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {c.pipeline && c.pipeline.length > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <div style={{ fontSize: 9, fontWeight: 800, color: "#a8a29e", letterSpacing: 1, marginBottom: 4, textTransform: "uppercase" }}>Pipeline</div>
                              {c.pipeline.map((p, j) => (
                                <div key={j} style={{ display: "grid", gridTemplateColumns: "160px 70px 50px 1fr", gap: 6, padding: "5px 8px", backgroundColor: "#fafaf9", borderRadius: 4, fontSize: 11, alignItems: "center", borderLeft: `3px solid ${p.conf >= 80 ? "#16a34a" : p.conf >= 50 ? "#d97706" : "#dc2626"}` }}>
                                  <span style={{ fontWeight: 600, color: "#1c1917" }}>{p.name}</span>
                                  <span style={{ color: "#78716c" }}>{p.eta}</span>
                                  <span style={{ color: p.conf >= 80 ? "#16a34a" : p.conf >= 50 ? "#d97706" : "#dc2626", fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>{p.conf}%</span>
                                  <span style={{ color: "#a8a29e", fontSize: 10 }}>{p.note}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          {c.subClusters && (
                            <div style={{ marginTop: 8 }}>
                              <div style={{ fontSize: 9, fontWeight: 800, color: "#a8a29e", letterSpacing: 1, marginBottom: 4, textTransform: "uppercase" }}>Sub-Clusters</div>
                              <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
                                <thead>
                                  <tr style={{ borderBottom: "2px solid #e7e5e4" }}>
                                    {["Location", "Acres", "Team", "Status"].map(h => (
                                      <th key={h} style={{ textAlign: "left", padding: "5px 8px", fontSize: 9, fontWeight: 700, color: "#a8a29e", textTransform: "uppercase" }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {c.subClusters.map((sub, si) => (
                                    <tr key={si} style={{ borderBottom: "1px solid #f5f5f4" }}>
                                      <td style={{ padding: "6px 8px", fontWeight: 500 }}>{sub.name}</td>
                                      <td style={{ padding: "6px 8px", fontFamily: "'IBM Plex Mono', monospace" }}>{sub.acres}</td>
                                      <td style={{ padding: "6px 8px", color: sub.team === "None" ? "#dc2626" : "#44403c" }}>{sub.team}</td>
                                      <td style={{ padding: "6px 8px" }}>
                                        <span style={{
                                          fontSize: 10, padding: "2px 8px", borderRadius: 4, fontWeight: 600,
                                          backgroundColor: sub.status.includes("COMPLETE") || sub.status.includes("WORKING") ? "#dcfce7" : sub.status.includes("NO") || sub.status.includes("LAST") || sub.status.includes("PASSED") || sub.status.includes("OVERDUE") ? "#fee2e2" : "#fef3c7",
                                          color: sub.status.includes("COMPLETE") || sub.status.includes("WORKING") ? "#16a34a" : sub.status.includes("NO") || sub.status.includes("LAST") || sub.status.includes("PASSED") || sub.status.includes("OVERDUE") ? "#dc2626" : "#92400e",
                                        }}>{sub.status}</span>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                          <div style={{ marginTop: 8, fontSize: 10, color: "#a8a29e" }}>🏠 {c.sheds} · Deposits: {c.deposits > 0 ? fmt(c.deposits) : "₹0"}</div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Section>
          </div>
        )}

        {/* DISPATCH TAB */}
        {tab === "dispatch" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>
            <Section title="Operating Plan: March 19-25" sub="Day-by-day priorities — next 7 days">
              <div style={{ display: "flex", gap: 4, marginBottom: 12, flexWrap: "wrap" }}>
                {WEEK_PLAN.map((d, i) => (
                  <button key={i} onClick={() => setXWeek(i)} style={{
                    padding: "6px 14px", fontSize: 11, fontWeight: 600, borderRadius: 6, cursor: "pointer",
                    border: `1px solid ${d.urgency === "critical" ? "#fecaca" : d.urgency === "high" ? "#fde68a" : "#e7e5e4"}`,
                    backgroundColor: xWeek === i ? (d.urgency === "critical" ? "#fee2e2" : d.urgency === "high" ? "#fef3c7" : "#f5f5f4") : "#fff",
                    color: xWeek === i ? "#1c1917" : "#78716c", fontFamily: "'Instrument Sans', sans-serif",
                  }}>
                    {d.day}
                  </button>
                ))}
              </div>
              {(() => {
                const d = WEEK_PLAN[xWeek];
                return (
                  <Card bg={d.urgency === "critical" ? "#fef2f2" : d.urgency === "high" ? "#fffbeb" : "#fff"} border={d.urgency === "critical" ? "#fecaca" : d.urgency === "high" ? "#fde68a" : "#e7e5e4"}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#1c1917" }}>{d.day}</div>
                      <div style={{ fontSize: 12, color: "#78716c" }}>{d.label}</div>
                      <Pill color={d.urgency === "critical" ? "#991b1b" : d.urgency === "high" ? "#92400e" : "#57534e"} bg={d.urgency === "critical" ? "#fee2e2" : d.urgency === "high" ? "#fef3c7" : "#f5f5f4"}>{d.urgency.toUpperCase()}</Pill>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {d.actions.map((a, j) => (
                        <div key={j} style={{ padding: "10px 12px", backgroundColor: a.priority === "P0" ? "#fef2f220" : "#fafaf9", borderRadius: 8, borderLeft: `3px solid ${a.priority === "P0" ? "#dc2626" : a.priority === "P1" ? "#d97706" : "#2563eb"}` }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                            <Pill color={a.priority === "P0" ? "#991b1b" : a.priority === "P1" ? "#92400e" : "#1e40af"} bg={a.priority === "P0" ? "#fee2e2" : a.priority === "P1" ? "#fef3c7" : "#dbeafe"}>{a.priority}</Pill>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "#1c1917", flex: 1 }}>{a.action}</div>
                            <div style={{ fontSize: 10, color: "#a8a29e" }}>{a.deadline}</div>
                          </div>
                          <div style={{ fontSize: 11, color: "#57534e", lineHeight: 1.5, marginBottom: 3 }}>{a.why}</div>
                          <div style={{ fontSize: 10, color: "#a8a29e" }}>Owner: {a.owner}</div>
                        </div>
                      ))}
                    </div>
                  </Card>
                );
              })()}
            </Section>

            <Section title="Payment Escalations" sub="All resolved or accepted">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {PAYMENT_ESCALATIONS.map((p, i) => (
                  <Card key={i} border={p.urgency === "resolved" ? "#bbf7d0" : "#e7e5e4"} bg={p.urgency === "resolved" ? "#f0fdf4" : "#fff"}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <div style={{ fontSize: 14, fontWeight: 700, color: "#1c1917" }}>{p.team}</div>
                      <Pill color={p.rec === "DONE" ? "#166534" : p.rec === "ACCEPTED" || p.rec === "PAID" ? "#1e40af" : "#991b1b"} bg={p.rec === "DONE" ? "#dcfce7" : p.rec === "ACCEPTED" || p.rec === "PAID" ? "#dbeafe" : "#fee2e2"}>{p.rec}</Pill>
                    </div>
                    <div style={{ fontSize: 11, color: "#57534e", marginBottom: 3 }}>Ask: {p.ask}</div>
                    <div style={{ fontSize: 11, color: "#57534e", marginBottom: 3 }}>Math: {p.math}</div>
                    <div style={{ fontSize: 11, color: p.urgency === "resolved" ? "#16a34a" : "#dc2626", marginBottom: 3, fontWeight: 600 }}>Impact: {p.impact}</div>
                    <div style={{ fontSize: 10, color: "#a8a29e" }}>Cost delta: {p.costDelta}</div>
                  </Card>
                ))}
              </div>
            </Section>

            {/* THIS WEEK — What Changed Section */}
            <Section title="What Changed (13 Mar → 19 Mar)" sub="Last 6 days">
              <Card bg="#eff6ff" border="#bfdbfe" style={{ marginBottom: 18 }}>
                <div style={{ fontSize: 10, fontWeight: 800, color: "#1e40af", letterSpacing: 1.5, marginBottom: 8, textTransform: "uppercase" }}>What Changed (13 Mar → 19 Mar)</div>
                {[
                  { text: "✅ Yashwant Shevare (30) ARRIVED Vadner 15 Mar. BIGGEST team. Transformative.", tag: "WIN" },
                  { text: "✅ Digambar Pawar (22) arrived Vadner 13 Mar. Working consistently 6 days.", tag: "WIN" },
                  { text: "✅ Umesh Khambait (9) — NEW permanent team finalized 17 Mar. Deployed to Jawalke Vani.", tag: "WIN" },
                  { text: "✅ 3 clusters COMPLETED: P.Garudeswar (26.75ac), Anjaneri (30.25ac), Puri (11ac).", tag: "WIN" },
                  { text: "✅ MRDBS partially recovered — 6.25ac done by Pushparaj (was 0 on 13 Mar).", tag: "WIN" },
                  { text: "✅ Sinner: 5 sub-clusters completed. 36ac done (was 9.75ac on 13 Mar).", tag: "WIN" },
                  { text: "✅ Total completed: 280ac (was ~150ac on 13 Mar). 87% increase in 6 days.", tag: "WIN" },
                  { text: "✅ Tata Strive team visited Vadner 18 Mar — impressed. External validation.", tag: "WIN" },
                  { text: "⚠️ Slack migration starting — field ops moving from WhatsApp. Transition period.", tag: "WATCH" },
                  { text: "⚠️ Vinod Wagh (15) postponed from 17th to 20th. Not confirmed.", tag: "WATCH" },
                  { text: "❌ Vitthal Pawar: 2 no-shows (14, 18 Mar). Effectively a ghost team.", tag: "LOSS" },
                  { text: "❌ Dhanraj Choudhary didn't come (14 Mar). Pundalik Raut took other work.", tag: "LOSS" },
                  { text: "❌ Hemraj Kadali missed 17 Mar — driver accident. Transport single-point failure.", tag: "LOSS" },
                  { text: "❌ Vijay Kalamkar (Mohadi) very frustrated — team didn't show 18 Mar.", tag: "LOSS" },
                ].map((a, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 4 }}>
                    <Pill color={a.tag === "WIN" ? "#166534" : a.tag === "WATCH" ? "#92400e" : "#991b1b"} bg={a.tag === "WIN" ? "#dcfce7" : a.tag === "WATCH" ? "#fef3c7" : "#fee2e2"}>{a.tag}</Pill>
                    <div style={{ fontSize: 12, color: "#1c1917", lineHeight: 1.5 }}>{a.text}</div>
                  </div>
                ))}
              </Card>
            </Section>
          </div>
        )}

        {/* TEAMS TAB */}
        {tab === "teams" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>
            <Section title="Active Teams" sub="Tier · Reliability · Payment · App">
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {TEAMS.map((t, i) => (
                  <Card key={i} style={{ borderLeft: `4px solid ${t.tier === 1 ? "#16a34a" : t.tier === 2 ? "#d97706" : "#dc2626"}`, animation: `fadeUp 0.3s ease ${i * 0.04}s both` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: "#1c1917" }}>{t.name}</span>
                        <span style={{ fontSize: 10, color: "#a8a29e" }}>({t.members}pax)</span>
                        <Pill color={t.tier === 1 ? "#16a34a" : t.tier === 2 ? "#92400e" : "#991b1b"} bg={t.tier === 1 ? "#dcfce7" : t.tier === 2 ? "#fef3c7" : "#fee2e2"}>T{t.tier}</Pill>
                        {t.pay === "ESCALATION" && <Pill color="#991b1b" bg="#fee2e2">PAY ISSUE</Pill>}
                        {t.app && <Pill color="#16a34a" bg="#dcfce7">APP ✓</Pill>}
                      </div>
                      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
                        <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, fontWeight: 700, color: "#2563eb", fontFamily: "'IBM Plex Mono', monospace" }}>{t.done}</div><div style={{ fontSize: 8, color: "#a8a29e", fontWeight: 700 }}>AC DONE</div></div>
                        <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, fontWeight: 700, color: "#78716c", fontFamily: "'IBM Plex Mono', monospace" }}>{t.days}d</div><div style={{ fontSize: 8, color: "#a8a29e", fontWeight: 700 }}>ACTIVE</div></div>
                        <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, fontWeight: 700, color: t.rel >= 85 ? "#16a34a" : t.rel >= 65 ? "#d97706" : "#dc2626", fontFamily: "'IBM Plex Mono', monospace" }}>{t.rel}%</div><div style={{ fontSize: 8, color: "#a8a29e", fontWeight: 700 }}>RELIABLE</div></div>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 12, marginTop: 6, fontSize: 10, color: "#78716c" }}>
                      <span>📍 {t.loc}</span>
                      <span>● <span style={{ color: sc[t.status] || "#78716c" }}>{t.status}</span></span>
                    </div>
                    {t.pay !== "OK" && <div style={{ marginTop: 4, fontSize: 10, color: t.pay === "ESCALATION" ? "#dc2626" : "#d97706" }}>💰 {t.payNote}</div>}
                    <div style={{ marginTop: 3, fontSize: 10, color: "#a8a29e" }}>⚠ {t.risk}</div>
                  </Card>
                ))}
              </div>
              <div style={{ marginTop: 14, padding: "12px 14px", backgroundColor: "#fff", borderRadius: 8, border: "1px solid #e7e5e4" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#a8a29e", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>Mukkadam App Rollout — 6/10 installed</div>
                <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
                  {TEAMS.map((t, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11 }}>
                      <div style={{ width: 10, height: 10, borderRadius: "50%", backgroundColor: t.app ? "#16a34a" : "#d6d3d1" }} />
                      <span style={{ color: t.app ? "#16a34a" : "#a8a29e" }}>{t.name.split(" ")[0]}</span>
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 10, color: "#a8a29e", marginTop: 4 }}>Target: 10/10 by 22 Mar. Umesh Khambait, Vinod Wagh, Hemraj Kadali, Khandu Kamdi still pending.</div>
              </div>
            </Section>

            <Section title="Team Allocation Timeline" sub="March 2026 — bars = assignments, gaps = idle risk">
              <Card style={{ overflowX: "auto" }}>
                <div style={{ minWidth: 960 }}>
                  <div style={{ display: "flex", marginBottom: 4, paddingLeft: 160 }}>
                    {ganttDays.map(d => (
                      <div key={d} style={{ width: 34, textAlign: "center", fontSize: 9, color: d === 19 ? "#dc2626" : "#a8a29e", fontWeight: d === 19 ? 700 : 400, fontFamily: "'IBM Plex Mono', monospace" }}>
                        {d}{d === 19 && <div style={{ fontSize: 7, color: "#dc2626" }}>TODAY</div>}
                      </div>
                    ))}
                  </div>
                  {TEAM_SCHEDULE.map((ts, ti) => {
                    const tierColors = { T1: "#16a34a", T2: "#2563eb", T3: "#dc2626", New: "#d97706" };
                    return (
                      <div key={ti} style={{ display: "flex", alignItems: "center", height: 32, borderBottom: "1px solid #f5f5f4" }}>
                        <div style={{ width: 160, flexShrink: 0, fontSize: 11, fontWeight: 600, color: "#44403c", display: "flex", alignItems: "center", gap: 6, paddingRight: 8 }}>
                          <span style={{ width: 7, height: 7, borderRadius: "50%", backgroundColor: tierColors[ts.t], flexShrink: 0, display: "inline-block" }} />
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ts.team}</span>
                        </div>
                        <div style={{ display: "flex", position: "relative", flex: 1 }}>
                          <div style={{ position: "absolute", left: `${(19 - 9) * 34 + 17}px`, top: 0, bottom: 0, width: 1.5, backgroundColor: "#dc2626", zIndex: 2, opacity: 0.3 }} />
                          {ganttDays.map(d => (
                            <div key={d} style={{ width: 34, height: 26, borderRight: "1px solid #fafaf9" }} />
                          ))}
                          {ts.d.map((seg, si) => {
                            const left = (seg[0] - 9) * 34;
                            const width = (seg[1] - seg[0] + 1) * 34 - 3;
                            const colors = ["#16a34a", "#2563eb", "#7c3aed", "#d97706"];
                            return (
                              <div key={si} title={`${seg[2]} (${seg[0]}–${seg[1]} Mar)`} style={{
                                position: "absolute", left: Math.max(left, 0), top: 3, height: 20, width: Math.max(width, 8),
                                backgroundColor: colors[si % colors.length], borderRadius: 4, opacity: 0.8,
                                display: "flex", alignItems: "center", paddingLeft: 5, overflow: "hidden",
                              }}>
                                <span style={{ fontSize: 8, color: "#fff", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{seg[2]}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                  <div style={{ display: "flex", gap: 16, marginTop: 10, fontSize: 10, color: "#a8a29e" }}>
                    {[{ c: "#16a34a", l: "T1 Proven" }, { c: "#2563eb", l: "T2 Moderate" }, { c: "#d97706", l: "New/Unproven" }, { c: "#dc2626", l: "T3 Unreliable" }].map((lg, i) => (
                      <span key={i} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", backgroundColor: lg.c, display: "inline-block" }} /> {lg.l}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            </Section>

            <Section title="Failed Pipeline — Last 14 Days" sub="10 teams = ~150 laborers = the capacity gap">
              <Card bg="#fef2f2" border="#fecaca">
                {FAILED_PIPELINE.map((f, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "170px 70px 1fr", gap: 6, padding: "6px 0", borderBottom: i < FAILED_PIPELINE.length - 1 ? "1px solid #fecaca" : "none", fontSize: 11, alignItems: "start" }}>
                    <span style={{ fontWeight: 600, color: "#991b1b" }}>{f.name}</span>
                    <span style={{ color: "#a8a29e" }}>{f.date}</span>
                    <div>
                      <div style={{ color: "#57534e" }}>{f.reason}</div>
                      <div style={{ color: "#92400e", fontSize: 10, marginTop: 2, fontStyle: "italic" }}>Lesson: {f.lesson}</div>
                    </div>
                  </div>
                ))}
                <div style={{ marginTop: 10, padding: "8px 10px", backgroundColor: "#fee2e2", borderRadius: 6, fontSize: 11, color: "#991b1b", fontWeight: 700 }}>
                  Pattern: up-down teams with transport costs are systematically unreliable. Permanent stationed teams convert at 2x the rate.
                </div>
              </Card>
            </Section>
          </div>
        )}

        {/* CLUSTERS TAB */}
        {tab === "clusters" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 20 }}>
              <KPI label="Total Pipeline" value="1,836 ac" sub="All stages" />
              <KPI label="Confirmed" value="683 ac" sub={`${CLUSTERS.reduce((s,c)=>s+c.farmers,0)} farmers`} />
              <KPI label="Completed" value={`${CLUSTERS.reduce((s,c)=>s+c.done,0).toFixed(0)} ac`} sub="41% of confirmed" color="#16a34a" />
              <KPI label="Deposits" value={fmt(CLUSTERS.reduce((s,c)=>s+c.deposits,0))} sub="collected" color="#2563eb" />
              <KPI label="Yet to Start" value={`${totalPending.toFixed(0)} ac`} sub="Fulfillment backlog" color="#dc2626" alert />
            </div>

            <Section title="Risk Assessment Matrix" sub="Every cluster, every dimension">
              <Card style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid #e7e5e4" }}>
                      {["Cluster", "Total", "Done", "%", "Team", "Shed", "Deposit", "Overall"].map(h => (
                        <th key={h} style={{ textAlign: "left", padding: "8px 6px", fontSize: 9, fontWeight: 700, color: "#a8a29e", textTransform: "uppercase", letterSpacing: 0.5 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {CLUSTERS.sort((a, b) => a.health === "critical" ? -1 : b.health === "critical" ? 1 : 0).map((c, i) => {
                      const rc = (level) => {
                        const m = { high: { c: "#991b1b", bg: "#fee2e2", l: "HIGH" }, med: { c: "#92400e", bg: "#fef3c7", l: "MED" }, low: { c: "#166534", bg: "#dcfce7", l: "LOW" } };
                        const s = m[level]; return <span style={{ padding: "2px 7px", borderRadius: 4, fontSize: 9, fontWeight: 700, backgroundColor: s.bg, color: s.c }}>{s.l}</span>;
                      };
                      const teamRisk = c.deployed.length === 0 ? "high" : c.deployed.reduce((s,t)=>s+t.members,0) < 10 ? "med" : "low";
                      const pct = c.total > 0 ? (c.done / c.total * 100) : 0;
                      const overall = c.health === "critical" ? "high" : c.health === "warning" ? "med" : "low";
                      return (
                        <tr key={c.id} style={{ borderBottom: "1px solid #f5f5f4", backgroundColor: overall === "high" ? "#fef2f2" : "transparent" }}>
                          <td style={{ padding: "8px 6px", fontWeight: 600, color: "#1c1917" }}>{c.name.length > 22 ? c.name.slice(0,22)+"…" : c.name}</td>
                          <td style={{ padding: "8px 6px", fontFamily: "'IBM Plex Mono', monospace" }}>{c.total}</td>
                          <td style={{ padding: "8px 6px", fontFamily: "'IBM Plex Mono', monospace" }}>{c.done}</td>
                          <td style={{ padding: "8px 6px", fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, color: pct < 10 ? "#dc2626" : "#1c1917" }}>{pct.toFixed(0)}%</td>
                          <td style={{ padding: "8px 6px" }}>{rc(teamRisk)}</td>
                          <td style={{ padding: "8px 6px" }}>{rc(c.deposits === 0 && c.total > 10 ? "high" : "low")}</td>
                          <td style={{ padding: "8px 6px" }}>{rc(c.deposits === 0 && c.total > 10 ? "high" : c.deposits > 0 ? "low" : "med")}</td>
                          <td style={{ padding: "8px 6px" }}>{rc(overall)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </Card>
            </Section>

            <Section title="Cluster Cards" sub="Click for details">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                {CLUSTERS.sort((a, b) => b.pending - a.pending).map((c, i) => {
                  const isOpen = selCluster === c.id;
                  const pct = c.total > 0 ? ((c.done / c.total) * 100) : 0;
                  const lab = c.deployed.reduce((s, t) => s + t.members, 0);
                  return (
                    <div key={c.id} onClick={() => setSelCluster(isOpen ? null : c.id)} style={{
                      backgroundColor: "#fff", borderRadius: 10, padding: 16, cursor: "pointer",
                      border: `1px solid ${isOpen ? "#1c1917" : c.health === "critical" ? "#fecaca" : "#e7e5e4"}`,
                      animation: `fadeUp 0.3s ease ${i * 0.03}s both`, transition: "border-color 0.2s",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "#1c1917" }}>{c.name.length > 22 ? c.name.slice(0,22)+"…" : c.name}</div>
                        <Pill color={hc[c.health]} bg={hbg[c.health]}>{c.health.toUpperCase()}</Pill>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 10 }}>
                        <div><div style={{ fontSize: 9, color: "#a8a29e", fontWeight: 600 }}>TOTAL</div><div style={{ fontSize: 15, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>{c.total}ac</div></div>
                        <div><div style={{ fontSize: 9, color: "#a8a29e", fontWeight: 600 }}>DONE</div><div style={{ fontSize: 15, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace", color: "#16a34a" }}>{c.done}ac</div></div>
                        <div><div style={{ fontSize: 9, color: "#a8a29e", fontWeight: 600 }}>LABOR</div><div style={{ fontSize: 15, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace", color: lab === 0 ? "#dc2626" : "#1c1917" }}>{lab}</div></div>
                      </div>
                      <div style={{ height: 4, backgroundColor: "#f5f5f4", borderRadius: 2, marginBottom: 8 }}>
                        <div style={{ height: "100%", width: `${Math.min(pct, 100)}%`, backgroundColor: hc[c.health], borderRadius: 2, transition: "width 0.4s" }} />
                      </div>
                      <div style={{ fontSize: 10, color: "#78716c" }}>
                        {c.deployed.length > 0 ? c.deployed.map(t => t.team).join(", ") : "No team"} · {c.farmers}f · {c.deposits > 0 ? fmt(c.deposits) : "₹0 deposit"}
                      </div>
                      {isOpen && (
                        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #e7e5e4", animation: "fadeUp 0.2s ease" }}>
                          {c.alerts.slice(0, 3).map((a, ai) => (
                            <div key={ai} style={{ fontSize: 11, color: "#dc2626", backgroundColor: "#fef2f2", padding: "4px 8px", borderRadius: 4, marginBottom: 3 }}>→ {a}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Section>
          </div>
        )}

        {/* BUSINESS TAB */}
        {tab === "business" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
              <KPI label="Total Tender Value" value="₹127L" sub="683 acres booked" />
              <KPI label="Deposits Collected" value="₹15.8L" sub="91 farmers · Avg ₹3,645/ac" color="#16a34a" />
              <KPI label="Uncollected" value="₹7.01L" sub="32 bookings · 2+ weeks old" color="#dc2626" alert />
              <KPI label="Missed Demand" value="133 ac" sub="Amit 108ac + Sarthak 25ac lost" color="#d97706" />
            </div>

            <Section title="Demand Team Performance">
              <Card>
                <div style={{ display: "grid", gridTemplateColumns: "90px 100px 80px 100px 100px 1fr", gap: 8, fontSize: 10, fontWeight: 700, color: "#a8a29e", padding: "4px 0", borderBottom: "2px solid #e7e5e4", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  <span>POC</span><span>Total Value</span><span>Total Ac</span><span>Sprint (2-9)</span><span>Missed</span><span></span>
                </div>
                {[
                  { poc: "Sarthak", val: 4226000, ac: 188.28, sprint: "₹21.3L/108ac", missed: "25ac" },
                  { poc: "Rohan", val: 2722000, ac: 111.3, sprint: "₹16.56L/75.5ac", missed: "—" },
                  { poc: "Amit", val: 3943000, ac: 202, sprint: "₹8.34L/47.5ac", missed: "108ac" },
                  { poc: "Sairaj", val: 1796000, ac: 80.08, sprint: "Narayangaon scouting 16/3", missed: "—" },
                ].map((s, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "90px 100px 80px 100px 100px 1fr", gap: 8, fontSize: 12, padding: "8px 0", borderBottom: "1px solid #f5f5f4", alignItems: "center" }}>
                    <span style={{ fontWeight: 600, color: "#1c1917" }}>{s.poc}</span>
                    <span style={{ color: "#16a34a", fontFamily: "'IBM Plex Mono', monospace" }}>{fmt(s.val)}</span>
                    <span style={{ color: "#57534e", fontFamily: "'IBM Plex Mono', monospace" }}>{s.ac}</span>
                    <span style={{ color: s.sprint.includes("₹0") ? "#dc2626" : "#44403c", fontSize: 11 }}>{s.sprint}</span>
                    <span style={{ color: s.missed !== "—" ? "#dc2626" : "#a8a29e", fontWeight: s.missed !== "—" ? 700 : 400 }}>{s.missed}</span>
                    <div style={{ height: 6, backgroundColor: "#f5f5f4", borderRadius: 3 }}>
                      <div style={{ width: `${(s.ac / 220) * 100}%`, height: "100%", borderRadius: 3, backgroundColor: "#2563eb" }} />
                    </div>
                  </div>
                ))}
                <div style={{ marginTop: 8, fontSize: 11, color: "#a8a29e" }}>
                  Total: ₹1.27Cr · 581.66ac · Target: 500 unique farmer tenders (currently ~137) · Missed: 133ac
                </div>
              </Card>
            </Section>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              <Section title="Pipeline Funnel" sub="1,836 total acres">
                <Card>
                  {PIPELINE_FUNNEL.map((p, i) => {
                    const pct = (p.acres / 1836 * 100).toFixed(1);
                    return (
                      <div key={i} style={{ marginBottom: 10 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 3 }}>
                          <span style={{ color: "#44403c", fontWeight: 500 }}>{p.stage}</span>
                          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, color: "#1c1917" }}>{p.acres.toLocaleString()} ac ({pct}%)</span>
                        </div>
                        <div style={{ height: 18, backgroundColor: "#f5f5f4", borderRadius: 4, overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${pct}%`, backgroundColor: p.color, borderRadius: 4, minWidth: p.acres > 0 ? 4 : 0 }} />
                        </div>
                      </div>
                    );
                  })}
                  <div style={{ marginTop: 10, padding: "8px 10px", backgroundColor: "#dcfce7", borderRadius: 6, fontSize: 11, color: "#166534" }}>
                    15.3% completed (was 8.2% on 13 Mar). 205ac confirmed but not started. Velocity improving.
                  </div>
                </Card>
              </Section>

              <Section title="Weekly Booking Volume" sub="Mar W1 was peak. W4-W5 stabilizing lower">
                <Card>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={WEEKLY_BOOKINGS}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f4" />
                      <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#a8a29e" }} />
                      <YAxis tick={{ fontSize: 10, fill: "#a8a29e" }} />
                      <Tooltip content={<CTooltip />} />
                      <Bar dataKey="acres" fill="#1c1917" name="Acres Booked" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </Card>
              </Section>
            </div>

            <Section title="Uncollected Deposits — ₹7.01L at Risk" sub="32 bookings, 2+ weeks old" urgent>
              <Card bg="#fef2f2" border="#fecaca">
                <div style={{ display: "grid", gridTemplateColumns: "50px 180px 70px 90px", gap: 6, fontSize: 10, fontWeight: 700, color: "#a8a29e", padding: "4px 0", borderBottom: "2px solid #fecaca", textTransform: "uppercase" }}>
                  <span>ID</span><span>Farmer</span><span>POC</span><span>Amount</span>
                </div>
                {UNCOLLECTED_DEPOSITS.map((d, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "50px 180px 70px 90px", gap: 6, fontSize: 11, padding: "5px 0", borderBottom: "1px solid #fef2f2", alignItems: "center" }}>
                    <span style={{ color: "#a8a29e", fontFamily: "'IBM Plex Mono', monospace" }}>{d.id}</span>
                    <span style={{ color: "#1c1917", fontWeight: 500 }}>{d.farmer}</span>
                    <span style={{ color: d.poc === "Amit" ? "#ea580c" : d.poc === "Sairaj" ? "#7c3aed" : "#2563eb", fontWeight: 600 }}>{d.poc}</span>
                    <span style={{ color: "#dc2626", fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>{fmt(d.amount)}</span>
                  </div>
                ))}
                <div style={{ marginTop: 10, display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                  <span style={{ color: "#991b1b", fontWeight: 700 }}>Total: {fmt(UNCOLLECTED_DEPOSITS.reduce((s, d) => s + d.amount, 0))}</span>
                  <span style={{ color: "#78716c" }}>Amit: {fmt(UNCOLLECTED_DEPOSITS.filter(d => d.poc === "Amit").reduce((s, d) => s + d.amount, 0))} · Sairaj: {fmt(UNCOLLECTED_DEPOSITS.filter(d => d.poc === "Sairaj").reduce((s, d) => s + d.amount, 0))} · Sarthak: {fmt(UNCOLLECTED_DEPOSITS.filter(d => d.poc === "Sarthak").reduce((s, d) => s + d.amount, 0))}</span>
                </div>
              </Card>
            </Section>

            <Section title="Next Week Pipeline — 665ac Visibility">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {[
                  { cluster: "Narayangaon", ac: 150, vis: "01/04", note: "Sairaj visited 16 Mar. First experience report shared. Bookings starting.", flag: true },
                  { cluster: "Sula", ac: 150, vis: "TBD", note: "About to book per Rohan. No concrete date.", flag: true },
                  { cluster: "Dindori", ac: 125, vis: "20/03", note: "Gaikwad Family 40ac, Nilwandi 6.8ac, Sonjamb, Mohadi overflow" },
                  { cluster: "Chandwad", ac: 100, vis: "25/03", note: "Pachorkar, Vakte, Shinde groups. Jaywant Shinde 8.75ac NEW" },
                  { cluster: "Sinnar", ac: 80, vis: "20/03", note: "Nanegaon 16ac, Kolhewadi 19.5ac, Vadgaon Landga 2.25ac" },
                  { cluster: "Niphad", ac: 60, vis: "25/03", note: "Sanjay Patil 35ac, Kushare Group. Kothure 1.95ac overdue." },
                ].map((p, i) => (
                  <Card key={i} border={p.flag ? "#fecaca" : "#e7e5e4"} bg={p.flag ? "#fef2f2" : "#fff"}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#1c1917" }}>{p.cluster}</div>
                      {p.flag && <Pill color="#991b1b" bg="#fee2e2">DEFER</Pill>}
                    </div>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "#2563eb", fontFamily: "'IBM Plex Mono', monospace", marginTop: 2 }}>{p.ac}ac</div>
                    <div style={{ fontSize: 10, color: "#a8a29e", marginTop: 2 }}>Visibility: {p.vis}</div>
                    <div style={{ fontSize: 10, color: "#78716c", marginTop: 2 }}>{p.note}</div>
                  </Card>
                ))}
              </div>
            </Section>

            <Card bg="#fff" border="#e7e5e4" style={{ marginTop: 4 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#1c1917", marginBottom: 10, fontFamily: "'Instrument Serif', Georgia, serif" }}>The Capacity Math</div>
              <div style={{ fontSize: 12, color: "#57534e", lineHeight: 1.7 }}>
                Current: Shevare(30) + Digambar(22) + Waghmare(14) + Bhoye(23) + Gaikwad(18) + Pithe(22) + P.Kadali(15) + Kamdi(10) + Khambait(9) + H.Kadali(18) = <strong style={{ color: "#1c1917" }}>181 laborers → ~120 ac/week</strong>
              </div>
              <div style={{ fontSize: 12, color: "#57534e", lineHeight: 1.7, marginTop: 4 }}>
                Incoming: Vinod Wagh(15) + Pandurang Deshmukh(~15) = <strong style={{ color: "#2563eb" }}>+30 if both arrive → 211 total → ~145 ac/wk</strong>
              </div>
              <div style={{ fontSize: 12, color: "#57534e", lineHeight: 1.7, marginTop: 4 }}>
                Pending: <strong style={{ color: "#dc2626" }}>~{totalPending.toFixed(0)} ac</strong>. At 120ac/wk: <strong style={{ color: "#d97706" }}>~{(totalPending/120).toFixed(1)} weeks</strong>. To keep pace with sales growth (665ac pipeline), <strong style={{ color: "#dc2626" }}>we need to scale to ~40 active teams from the current 10</strong>.
              </div>
              <div style={{ marginTop: 10, padding: "10px 14px", backgroundColor: "#eff6ff", borderRadius: 8, fontSize: 12, color: "#1e40af", lineHeight: 1.6 }}>
                <strong>The metric that matters:</strong> What % of committed farmers got their team on scheduled date? Currently: <strong style={{ color: "#16a34a" }}>~55%</strong> (up from 45% on 13 Mar). 130ac completed in 6 days = <strong>21.7ac/day</strong>. The system IS working.
              </div>
            </Card>
          </div>
        )}

        {/* STRATEGY TAB */}
        {tab === "strategy" && (
          <div style={{ animation: "fadeUp 0.3s ease" }}>

            <Section title="Data Quality Issues" sub={`${DATA_QUALITY.length} active — affecting allocation accuracy`}>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {DATA_QUALITY.map((d, i) => (
                  <Card key={i} style={{ display: "grid", gridTemplateColumns: "1fr 90px", gap: 8, fontSize: 11, alignItems: "start" }}>
                    <div>
                      <div style={{ fontWeight: 600, color: "#1c1917" }}>{d.issue}</div>
                      <div style={{ color: "#dc2626", fontSize: 10, marginTop: 2 }}>Impact: {d.impact}</div>
                    </div>
                    <div style={{ color: "#a8a29e", fontSize: 10, textAlign: "right" }}>Owner: {d.owner}</div>
                  </Card>
                ))}
              </div>
            </Section>

            <Section title="Strategic Risks">
              {[
                { sev: "CRITICAL", color: "#dc2626", title: "Supply-Demand Gap — 3x Mismatch Persists",
                  detail: `${totalPending.toFixed(0)}ac pending across ${CLUSTERS.length} clusters. 181 laborers = ~120ac/wk capacity. Vadner alone has 152ac with 52 laborers — 15+ weeks at current pace. Even with incoming teams (Vinod Wagh 15, Pandurang ~15), gap remains massive. Pipeline adds 665ac more.`,
                  action: "Scale to ~40 active teams (from 10). Station ALL teams permanently — up-down model proven to fail. Prioritize Vadner reinforcement. Aggressive sourcing: Sahyadri sheet, pack house visits, Sarvam leads." },
                { sev: "CRITICAL", color: "#dc2626", title: "Up-Down Team Model Systematically Failing",
                  detail: "Clear pattern across 6 weeks: Vitthal Pawar 2 no-shows (14, 18 Mar). Hemraj Kadali missed 17 Mar (driver accident). Vilas Pawar harvesting instead of our work. Every up-down team has a >40% failure rate. Transport-dependent teams prioritize their own convenience over our commitments.",
                  action: "POLICY: Only permanent stationed teams for ALL new deployments. Resolve Vitthal by 20 Mar — station or release. Fix Hemraj Kadali transport (alternate vehicle or station). Convert remaining up-down teams to permanent." },
                { sev: "HIGH", color: "#d97706", title: "Booking Velocity in Free-Fall",
                  detail: "Mar W1: 358ac → W2: 200ac → W3: 77ac → W4: 23ac → W5: 8ac. Bookings have collapsed 97% from peak. Pipeline leads (1,401ac) not converting to confirmed bookings. If this trend holds, we run out of confirmed work in 3-4 weeks even as capacity grows.",
                  action: "Push 150 Facebook CNC leads (Komal report 16 Mar). Sairaj: convert Narayangaon scouting (16 Mar) into deposits. Amit/Sarthak: close Mar 1-18 open leads by 20 Mar. Reactivate Krushikumbh contacts. Consider pricing adjustments for April bookings." },
                { sev: "HIGH", color: "#d97706", title: "Farmer Communication — Still Breaking Promises",
                  detail: "Vijay Kalamkar: team scheduled 18th, no-show, farmer sharing angry messages. Anil Kad: 6 days cordon tying overdue. Rohan Mogal (Niphad): 9 days zero response. Dhananjay Jadhav: team arrived but farmer wasn't informed. Pattern: we commit dates we can't keep.",
                  action: "Amit's own request (18 Mar): 'Inform farmers 1 day before team arrival.' Implement as mandatory SOP. Vivek: daily farmer status calls. Never commit a date unless team is confirmed AND stationed. Under-promise, over-deliver." },
                { sev: "MEDIUM", color: "#2563eb", title: "Non-Pruning Revenue — New Stream Starting 20 Mar",
                  detail: "Pasting, stem tying, leaf removal, cordon tying activities now live. Bablu Wagh (pasting), Bansidhar Pawar (leaf removal by scissors), Nilesh Keda Chavan (full non-pruning), Alka Wagh (pasting). Lower labor intensity = higher per-team output. Female teams viable for non-pruning.",
                  action: "Book tender-without-pruning at tender rates (Azhaan approved). Use non-pruning to keep teams busy during pruning gaps. Female teams for cordon tying/pasting — 2 contacts shared by Vivek. This expands addressable market without needing more pruning teams." },
                { sev: "POSITIVE", color: "#16a34a", title: "System Working — 130ac in 6 Days, 3 Clusters Completed",
                  detail: "280ac done (was ~150 on 13 Mar). 87% increase. P.Garudeswar, Anjaneri, Puri = 3 clusters 100% complete. 5 Sinner sub-clusters done. MRDBS partially recovered. 61 new laborers added (Shevare 30, Digambar 22, Khambait 9). Farmer delivery rate: 45% → ~55%. Tata Strive impressed on 18 Mar visit.",
                  action: "Lock in momentum. Vinod Wagh (20 Mar) and Pandurang Deshmukh are next. Non-pruning revenue starts 20 Mar. Narayangaon 150ac = biggest April opportunity. The machine is working — now it needs to scale." },
              ].map((r, i) => (
                <Card key={i} bg={r.sev === "CRITICAL" ? "#fef2f2" : r.sev === "HIGH" ? "#fffbeb" : r.sev === "POSITIVE" ? "#f0fdf4" : "#eff6ff"} border={r.sev === "CRITICAL" ? "#fecaca" : r.sev === "HIGH" ? "#fde68a" : r.sev === "POSITIVE" ? "#bbf7d0" : "#bfdbfe"} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <Pill color={r.color} bg={r.color + "18"}>{r.sev}</Pill>
                    <span style={{ fontSize: 14, fontWeight: 700, color: "#1c1917" }}>{r.title}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#57534e", lineHeight: 1.6, marginBottom: 8 }}>{r.detail}</div>
                  <div style={{ fontSize: 12, color: r.color, lineHeight: 1.6, padding: "8px 10px", backgroundColor: r.color + "0a", borderRadius: 6 }}>
                    <strong>ACTION:</strong> {r.action}
                  </div>
                </Card>
              ))}
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}
