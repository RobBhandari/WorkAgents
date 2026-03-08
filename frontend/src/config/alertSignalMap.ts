// Maps alert dashboard IDs to the signals that contribute to them.
// direction: "up" = metric rising is bad, "down" = metric falling is bad
export const alertSignalMap: Record<string, { id: string; label: string; direction: 'up' | 'down' }[]> = {
  security: [
    { id: 'exploitable', label: 'Exploitable vulnerabilities', direction: 'up' },
    { id: 'security-infra', label: 'Infra security posture', direction: 'down' },
    { id: 'target', label: 'Security target gap', direction: 'up' },
  ],
  deployment: [
    { id: 'flow', label: 'Flow efficiency', direction: 'down' },
    { id: 'deployment', label: 'Deployment frequency', direction: 'down' },
    { id: 'bugs', label: 'Bug rate', direction: 'up' },
  ],
  flow: [
    { id: 'flow', label: 'Flow efficiency', direction: 'down' },
    { id: 'collaboration', label: 'Collaboration health', direction: 'down' },
  ],
  bugs: [
    { id: 'bugs', label: 'Bug rate', direction: 'up' },
    { id: 'risk', label: 'Risk score', direction: 'up' },
  ],
  ownership: [
    { id: 'ownership', label: 'Ownership coverage', direction: 'down' },
    { id: 'risk', label: 'Risk score', direction: 'up' },
    { id: 'collaboration', label: 'Collaboration health', direction: 'down' },
  ],
  risk: [
    { id: 'risk', label: 'Risk score', direction: 'up' },
    { id: 'bugs', label: 'Bug rate', direction: 'up' },
    { id: 'deployment', label: 'Deployment frequency', direction: 'down' },
    { id: 'ownership', label: 'Ownership coverage', direction: 'down' },
  ],
  collaboration: [
    { id: 'collaboration', label: 'Collaboration health', direction: 'down' },
    { id: 'ownership', label: 'Ownership coverage', direction: 'down' },
  ],
};
