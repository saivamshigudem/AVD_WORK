"""Helper script to set up Peer Review Agent configuration."""
import os
from pathlib import Path


def create_env_file():
    """Create .env file from user input."""
    print("=" * 60)
    print("Peer Review Agent - Setup Helper")
    print("=" * 60)
    print()
    
    env_path = Path(".env")
    if env_path.exists():
        response = input(".env file already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Skipping .env file creation.")
            return
    
    print("Please provide the following information:")
    print()
    
    # Azure DevOps Configuration
    print("Azure DevOps Configuration:")
    org_url = input("Organization URL (e.g., https://dev.azure.com/YourOrg): ").strip()
    project = input("Project Name: ").strip()
    pat = input("Personal Access Token (PAT): ").strip()
    print()
    
    # OpenAI Configuration
    print("OpenAI Configuration:")
    openai_key = input("OpenAI API Key: ").strip()
    print()
    
    # Optional Azure OpenAI
    use_azure = input("Use Azure OpenAI? (y/n): ").strip().lower() == 'y'
    azure_endpoint = ""
    azure_key = ""
    azure_version = ""
    
    if use_azure:
        azure_endpoint = input("Azure OpenAI Endpoint: ").strip()
        azure_key = input("Azure OpenAI API Key: ").strip()
        azure_version = input("Azure OpenAI API Version (default: 2024-02-15-preview): ").strip() or "2024-02-15-preview"
    
    # Write .env file
    env_content = f"""# Azure DevOps Configuration
AZURE_DEVOPS_ORG={org_url}
AZURE_DEVOPS_PROJECT={project}
AZURE_DEVOPS_PAT={pat}

# OpenAI Configuration
OPENAI_API_KEY={openai_key}
"""
    
    if use_azure:
        env_content += f"""
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT={azure_endpoint}
AZURE_OPENAI_API_KEY={azure_key}
AZURE_OPENAI_API_VERSION={azure_version}
"""
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print()
    print(f"✅ Created .env file at {env_path.absolute()}")
    print()
    print("⚠️  IMPORTANT: Add .env to .gitignore to keep your credentials secure!")
    print()


def update_config_yaml():
    """Update config.yaml with basic settings."""
    config_path = Path("config.yaml")
    
    if not config_path.exists():
        print("config.yaml not found. Please create it manually.")
        return
    
    print()
    print("Would you like to update config.yaml with basic settings? (y/n): ", end="")
    response = input().strip().lower()
    
    if response == 'y':
        # Read current config
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        
        # Update with defaults if not set
        if not config.get("azure_devops", {}).get("organization"):
            org = input("Azure DevOps Organization URL: ").strip()
            if org:
                config.setdefault("azure_devops", {})["organization"] = org
        
        if not config.get("azure_devops", {}).get("project"):
            project = input("Azure DevOps Project Name: ").strip()
            if project:
                config.setdefault("azure_devops", {})["project"] = project
        
        # Write back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        print(f"✅ Updated {config_path}")
    else:
        print("Skipping config.yaml update.")


def main():
    """Main setup function."""
    print()
    create_env_file()
    update_config_yaml()
    
    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Review and customize guidelines.json for your coding standards")
    print("2. Review config.yaml for additional settings")
    print("3. Run: python src/main.py --help")
    print()


if __name__ == "__main__":
    main()

