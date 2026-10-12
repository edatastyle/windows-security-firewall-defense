# Contributing to Windows Security Firewall Defense

Thank you for your interest in contributing to **Windows Security Firewall Defense**! Contributions that improve security, reliability, usability, documentation, and testing are welcome.

Please read these guidelines before opening an issue or submitting a pull request.

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)
- [Development Environment](#development-environment)
- [Code Guidelines](#code-guidelines)
- [Security and Safety](#security-and-safety)
- [Testing](#testing)
- [Pull Requests](#pull-requests)
- [Reporting Security Vulnerabilities](#reporting-security-vulnerabilities)
- [Community Guidelines](#community-guidelines)
- [License](#license)

## Ways to Contribute

You can contribute by:

- Fixing bugs and improving existing functionality.
- Improving Windows Firewall rule management.
- Enhancing security checks, logging, and reporting.
- Improving PowerShell scripts and application components.
- Improving compatibility with supported Windows versions.
- Adding tests and troubleshooting instructions.
- Improving installation and configuration documentation.
- Reviewing issues and testing proposed changes.

For significant changes, open an issue first to discuss your proposed approach.

## Reporting Bugs

Before opening a bug report, check the [existing GitHub issues](https://github.com/edatastyle/windows-security-firewall-defense/issues) to avoid duplicates.

Include the following information:

- A clear description of the problem.
- Windows edition, version, and build.
- Relevant PowerShell and dependency versions.
- Steps to reproduce the issue.
- Expected and actual behavior.
- Relevant error messages and sanitized logs.
- Troubleshooting steps already attempted.

Do not include passwords, access tokens, private keys, or sensitive network information in public reports.

## Requesting Features

When suggesting a feature, explain:

1. The problem it solves.
2. The expected behavior.
3. The benefits for users.
4. Alternative approaches considered.
5. Potential security, performance, and compatibility implications.

Features should support legitimate defensive security and authorized administration of Windows systems.

## Development Environment

### Prerequisites

Depending on the component being modified, you may need:

- Git.
- A supported Windows installation or Windows virtual machine.
- The PowerShell version required by the project.
- Relevant programming language runtimes and dependencies.
- Administrator privileges when testing firewall operations requires elevation.

Review the repository's README and configuration files to identify the actual requirements and supported versions.

### Clone the Repository

```powershell
git clone https://github.com/edatastyle/windows-security-firewall-defense.git
Set-Location windows-security-firewall-defense
```

Review the documentation and inspect scripts before executing them.

**Important:** Firewall changes can interrupt network connectivity and remote administration. Use a dedicated test machine or virtual machine whenever possible, and maintain a recovery method before testing security-related changes.

### Create a Branch

Create a separate branch for each contribution:

```powershell
git switch -c fix/short-description
```

Examples:

```powershell
git switch -c fix/firewall-rule-validation
git switch -c feature/security-reporting
git switch -c docs/installation-guide
```

## Code Guidelines

### General

- Keep changes focused and easy to review.
- Follow existing project conventions.
- Use descriptive names and meaningful comments.
- Handle errors explicitly and provide useful messages.
- Validate user input and external data.
- Avoid unnecessary dependencies and unrelated refactoring.
- Update documentation when behavior or configuration changes.
- Never commit credentials, private keys, personal data, or sensitive logs.

### PowerShell

- Follow consistent PowerShell formatting and naming conventions.
- Use approved verbs for function names where practical.
- Validate parameters and external input.
- Avoid unsafe command construction and untrusted script execution.
- Check command results and handle errors appropriately.
- Use `-ErrorAction Stop` where terminating error handling is required.
- Avoid unnecessary administrator privileges.
- Keep functions focused and maintainable.

### Windows Firewall and Security

- Apply the principle of least privilege.
- Avoid unnecessarily broad firewall rules.
- Do not silently disable Windows Firewall, Microsoft Defender, or other security controls.
- Document changes to firewall rules and system settings.
- Preserve existing configuration unless modification is necessary.
- Make security-relevant operations understandable and reversible where practical.
- Provide clear warnings before potentially disruptive operations.
- Avoid exposing sensitive system information in logs or reports.

## Security and Safety

Security is central to this project. All contributions must follow these principles:

- Use the software only on systems and networks you own or are authorized to administer.
- Request elevated privileges only when necessary.
- Validate inputs before passing them to PowerShell, command-line utilities, or system APIs.
- Never hardcode credentials or authentication tokens.
- Do not introduce covert monitoring or unauthorized access mechanisms.
- Do not weaken security protections to make a feature work.
- Avoid destructive changes without safeguards and clear explanations.
- Document the expected impact of changes to firewall rules and system configuration.

Any feature that creates, modifies, or removes firewall rules should explain its purpose, scope, and potential impact.

## Testing

Before submitting a pull request, run the relevant tests and verify that existing functionality remains intact.

Depending on the change, test:

- Application or script startup.
- Firewall rule creation, inspection, modification, and removal.
- Input validation and error handling.
- Behavior when administrator privileges are unavailable.
- Compatibility with supported Windows and PowerShell versions.
- Logging and reporting behavior.
- Preservation of existing firewall configuration.
- Recovery from failed or interrupted operations.

### PowerShell Syntax Validation

You can use the PowerShell parser to check `.ps1` files for syntax errors:

```powershell
$files = Get-ChildItem -Path . -Recurse -Filter *.ps1

foreach ($file in $files) {
    $tokens = $null
    $errors = $null

    [System.Management.Automation.Language.Parser]::ParseFile(
        $file.FullName,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null

    if ($errors.Count -gt 0) {
        Write-Host "Syntax errors in $($file.FullName)" -ForegroundColor Red
        $errors | ForEach-Object {
            Write-Host $_.Message
        }
    }
}
```

This checks syntax only. It does not verify runtime behavior or guarantee that a script is secure.

If you cannot run a test because of environment or hardware limitations, explain that clearly in your pull request.

## Pull Requests

Before opening a pull request:

1. Review your changes and remove unrelated modifications.
2. Ensure no credentials or sensitive information are included.
3. Run the relevant tests and syntax checks.
4. Update documentation where necessary.
5. Commit your changes with a descriptive message.
6. Push your branch and open a pull request against the repository's target branch.

Example:

```powershell
git add .
git commit -m "Improve firewall rule validation"
git push -u origin fix/firewall-rule-validation
```

Include the following information in your pull request:

- **Summary:** What changed and why.
- **Related issue:** Link to an existing issue, if applicable.
- **Implementation:** Important technical details.
- **Security impact:** Firewall rules or system settings affected.
- **Testing:** Checks performed and their results.
- **Compatibility:** Windows and PowerShell versions tested.
- **Recovery:** Instructions for reversing potentially disruptive changes.

Keep pull requests focused and respond constructively to review feedback. Maintainers may request revisions before merging.

## Reporting Security Vulnerabilities

Please do not disclose exploitable vulnerabilities in public issues.

Use GitHub's private vulnerability reporting feature for this repository, if available. Otherwise, contact the maintainer through an established private channel.

Include the affected component, potential impact, reproduction steps, affected versions, and suggested mitigations when possible.

Allow the maintainer reasonable time to investigate and address the issue before publicly disclosing sensitive details.

## Community Guidelines

Help maintain a respectful and collaborative environment:

- Be courteous and professional.
- Welcome contributors with different experience levels.
- Focus feedback on code and technical decisions rather than individuals.
- Explain disagreements constructively.
- Respect privacy and confidentiality.
- Avoid harassment, personal attacks, and spam.

## License

By submitting a contribution, you agree that it may be distributed under the license governing this repository. Review the repository's `LICENSE` file before contributing.

If no license is present, contact the maintainer for clarification before submitting work intended for distribution.

Thank you for helping improve Windows Security Firewall Defense!

**Repository:** https://github.com/edatastyle/windows-security-firewall-defense
