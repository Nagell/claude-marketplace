## MODIFIED Requirements

### Requirement: Counterpart question only with a counterpart
Before the step 0 dialog the skill SHALL run only the local rules lookup. In that dialog it SHALL ask the counterpart question only when the rules file has a `## Counterpart` section.

#### Scenario: No counterpart in the rules
- **WHEN** a review starts and a rules file exists without a `## Counterpart` section
- **THEN** the dialog asks only the engine and effort questions, and step 1a is skipped

#### Scenario: No rules file
- **WHEN** a review starts, there is no rules file and the repo is not declined
- **THEN** the dialog asks the engine and effort questions and whether to create a rules file from the template

## ADDED Requirements

### Requirement: Rules template
The skill SHALL ship a rules template that holds every section of the rules format, each with a comment saying what it does and that it may be left out. The `## Counterpart` section SHALL be inside a comment, so an unedited copy reads as having no counterpart.

#### Scenario: Unedited copy
- **WHEN** the template is copied to `~/.claude/review-rules/<repo>.md` unchanged except the Repos row
- **THEN** the rules lookup finds it and reports no counterpart

### Requirement: Create rules on first review
When the user accepts the offer, the skill SHALL copy the template to the expected path, creating the rules folder when missing and without overwriting an existing file, and fill the Repos row with the repo name, local checkout and project id, leaving the worktree base to its `<checkout>.worktrees/` default. A value it cannot find out SHALL be written as `-`, which a later run reads as not set, never as a placeholder.

#### Scenario: Prefilled copy
- **WHEN** the user accepts in a repo with no rules file
- **THEN** the file exists at the expected path with this repo's name, checkout and project id in the Repos row and no worktree base

### Requirement: Fill and continue
After creating the file, the skill SHALL show its path and content, ask whether the repo has a paired repo (unless a second MR URL or `--both` already names it), then ask whether to add anything else, write each answer into the matching section and show the change. It SHALL then rerun the rules lookup and continue the review with the new file.

#### Scenario: Paired repo named
- **WHEN** the user accepts and names a paired repo
- **THEN** the file gets a live `## Counterpart` section for that repo, the rules lookup reports a counterpart and the counterpart question is asked in the same run

#### Scenario: Nothing to add
- **WHEN** the user accepts, names no paired repo and adds nothing
- **THEN** the file keeps the template's commented sections and the review continues without a counterpart

#### Scenario: File appeared meanwhile
- **WHEN** a file exists at the expected path by the time it would be written
- **THEN** the skill does not overwrite it, says so and reruns the rules lookup

### Requirement: Remember a declined offer
When the user declines, the skill SHALL add the repo name to `.declined` in the rules folder, one name per line, creating both when missing, and SHALL NOT offer again for a repo listed there. The rules lookup SHALL report whether the repo is listed, and SHALL report an unreadable list instead of treating it as empty.

#### Scenario: Declined repo
- **WHEN** a review starts for a repo listed in `.declined` that has no rules file
- **THEN** the dialog has no create question and the no-rules notice says how to be asked again

#### Scenario: Rules file exists
- **WHEN** a repo has a rules file, listed in `.declined` or not
- **THEN** no create question is asked
