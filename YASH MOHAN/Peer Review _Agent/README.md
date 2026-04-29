# Peer Review Agent

An automated peer review system that analyzes code against Azure DevOps user stories and coding guidelines, suggests fixes, and creates pull requests.

## Features

- **Azure DevOps Integration**: Authenticates with Azure DevOps using Personal Access Tokens (PAT)
- **User Story Fetching**: Automatically retrieves user stories related to the current branch or PR
- **Code Analysis**: Uses LLM (GPT-4) with RAG approach to analyze code against:
  - User story acceptance criteria
  - Coding guidelines and standards
  - Security best practices
  - Performance considerations
- **Automated Fixes**: Suggests and optionally applies code fixes
- **Git Operations**: Commits fixes to new branches and pushes to Azure DevOps
- **PR Management**: Creates pull requests with detailed reports
- **Report Generation**: Generates comprehensive markdown reports

## Prerequisites

- Python 3.8 or higher
- Azure DevOps account with Personal Access Token (PAT)
- OpenAI API key (or Azure OpenAI endpoint)
- Git repository initialized

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd Peer-Review-Agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your environment:
   - Run the interactive setup: `python scripts/setup_helper.py`
   - Or manually create `.env` file in the root directory with your credentials:
     ```env
     AZURE_DEVOPS_ORG=https://dev.azure.com/YourOrg
     AZURE_DEVOPS_PROJECT=YourProject
     AZURE_DEVOPS_PAT=your_pat_here
     OPENAI_API_KEY=your_openai_key_here
     ```
   - Edit `config.yaml` with your project settings (optional)
   - Customize `guidelines.json` with your coding standards (optional)

4. Test your setup:
```bash
python scripts/auto_agent_demo.py
```

## Configuration

### Environment Variables (.env)

```env
# Azure DevOps Configuration
AZURE_DEVOPS_ORG=https://dev.azure.com/YourOrg
AZURE_DEVOPS_PROJECT=YourProject
AZURE_DEVOPS_PAT=your_personal_access_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

### Configuration File (config.yaml)

Edit `config.yaml` to configure:
- Azure DevOps organization and project
- LLM provider and model settings
- Code analysis settings (file patterns, limits)
- Git and review settings
- Report output directory

### Guidelines (guidelines.json)

Customize `guidelines.json` to define:
- Coding standards (indentation, naming conventions)
- Documentation requirements
- Error handling rules
- Security requirements
- Testing requirements
- User story compliance rules

## Usage

### Basic Usage
    
Run the peer review agent:
```bash
python -m src.main
```

Or use the demo script to test setup:
```bash
python scripts/auto_agent_demo.py
```

### Command Line Options

```bash
python -m src.main --help
```

Options:
- `--config PATH`: Path to configuration file (default: config.yaml)
- `--env PATH`: Path to .env file (default: .env)
- `--branch BRANCH`: Branch name to review (defaults to current branch)
- `--auto-apply`: Auto-apply fixes without confirmation
- `--no-auto-apply`: Do not auto-apply fixes (override config)

### Examples

Review current branch with auto-apply:
```bash
python -m src.main --auto-apply
```

Review specific branch:
```bash
python -m src.main --branch feature/user-authentication
```

Review without applying fixes:
```bash
python -m src.main --no-auto-apply
```

## Workflow

1. **Authentication**: Authenticates with Azure DevOps using PAT
2. **Fetch User Stories**: Retrieves user stories related to the current branch
3. **Load Code**: Loads changed files from the workspace
4. **Analyze**: Analyzes code against user stories and guidelines using LLM
5. **Apply Fixes**: Optionally applies suggested fixes
6. **Generate Report**: Creates a markdown report with findings
7. **Commit & Push**: Commits fixes to a new branch and pushes to Azure DevOps
8. **Create PR**: Creates a pull request with the report attached

## Report Structure

The generated report includes:
- Summary of issues (by severity)
- User stories reviewed
- User story compliance status
- Detailed issues with suggested fixes
- Applied fixes summary
- Recommendations

## Architecture

```
src/
├── main.py                 # Main orchestrator
├── config_loader.py        # Configuration management
├── azure_auth.py           # Azure DevOps authentication
├── user_story_fetcher.py   # User story retrieval
├── code_loader.py          # Code file loading
├── code_analyzer.py        # LLM-based code analysis
├── fix_applier.py          # Fix application
├── git_operations.py       # Git operations
├── pr_manager.py           # Pull request management
└── report_generator.py     # Report generation
```

## Security Considerations

- **PAT Management**: Store PATs securely in `.env` file (never commit to git)
- **Token Refresh**: Implement token refresh logic for long-running processes
- **Input Validation**: All inputs are validated and sanitized
- **Error Handling**: Comprehensive error handling prevents information leakage

## Troubleshooting

### Authentication Issues

- Verify your PAT has the required permissions:
  - Code (read & write)
  - Work items (read)
  - Pull requests (read & write)
- Check that your organization URL is correct
- Ensure your PAT hasn't expired

### No User Stories Found

- Check branch naming conventions (e.g., `feature/US-123`)
- Verify user stories are linked to commits
- Try fetching recent active stories instead

### LLM Analysis Errors

- Verify your OpenAI API key is valid
- Check API rate limits
- Ensure sufficient API credits

### Git Operations Failures

- Ensure you're in a git repository
- Check git credentials are configured
- Verify remote repository access

## Limitations

- **Token Expiry**: PATs may expire; implement refresh logic
- **Complex Mapping**: User story mapping relies on branch naming or commit links
- **LLM Context**: Large codebases may exceed context limits
- **Performance**: Analysis time increases with code size
- **Over-fixing**: Manual review recommended before auto-applying fixes

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify your license here]

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section
- Review Azure DevOps and OpenAI documentation

