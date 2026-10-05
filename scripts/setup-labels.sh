#!/usr/bin/env bash
# Setup script for AI Engineering Team labels
# Run once after merging the AI Engineering Team PR
# Usage: bash scripts/setup-labels.sh

set -euo pipefail

REPO="${1:?Usage: setup-labels.sh <owner/repo>}"

echo "Creating labels for repository: $REPO"

# Define labels: name, color, description
declare -a labels=(
  "automation/n-omega:0366d6:Issue from N-Omega Supervisor audit"
  "ai-team/in-progress:ffd700:AI team is actively working on this issue"
  "ai-team/needs-human:ff0000:AI team escalated - needs human review and decision"
  "ai-team/attempt:a0826d:Marker for AI team attempt counter (internal use)"
  "governance-change:8f1493:Governance policy or authorization change - requires review"
)

for label_spec in "${labels[@]}"; do
  IFS=: read -r name color description <<< "$label_spec"
  
  echo ""
  echo "Creating label: $name"
  echo "  Color: #$color"
  echo "  Description: $description"
  
  # Use GitHub CLI to create the label
  if command -v gh &> /dev/null; then
    gh label create "$name" \
      --repo "$REPO" \
      --color "$color" \
      --description "$description" 2>/dev/null || {
      echo "  ℹ️  Label '$name' already exists or gh is not authenticated"
    }
  else
    echo "  ⚠️  GitHub CLI (gh) not found. Please create labels manually:"
    echo "     https://github.com/$REPO/labels"
    exit 1
  fi
done

echo ""
echo "✅ Label setup complete!"
echo ""
echo "Next steps:"
echo "1. Enable Copilot coding agent:"
echo "   https://github.com/$REPO/settings/integrations"
echo "2. Merge the AI Engineering Team PR"
echo "3. Test with workflow_dispatch: https://github.com/$REPO/actions/workflows/ai-engineering-team.yml"
