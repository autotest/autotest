Life cycle of an idea in autotest
=================================

If you are wondering how to propose
an idea and work through its completion
(feature making its way to a stable release),
here is a small schema of how ideas transition
to working code in the autotest developer community:


1. RFC email to the mailing list
2. Allow 2-3 days for feedback. RFC's often have a lower priority than bugs and usage problems.
3. Open github issues according to results of discussion
4. Create patchsets that implement solutions to the github issues
5. Review, fix comments, resend, until the patches are deemed good by the maintainers
6. Patchsets go to the next branch
7. Next branch gets tested/scrutinized by automated scripts
8. If needed, more bugfix iterations to fix the problems
9. next gets merged to master
10. master at some point is tagged as a stable autotest release

Although it seems convoluted, no one is stopping you from starting to design and implement your feature, and sending it straight away to github/mailing list (start on step 4). The maintainers will have to analyze and make judgement calls of whether the feature fits the current state of project, reason why it is more advisable to check on the feasibility before starting to spend too much energy implementing things.

You can see what to verify before sending patches in
:doc:`the submission checklist page <SubmissionChecklist>`,
and if you are new to git, you can read
:doc:`the git workflow page <../developer/GitWorkflow>`.
