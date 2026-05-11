import type { Linter, Rule } from 'eslint';

declare const plugin: {
  readonly meta: {
    readonly name: 'mutation-method-blocker';
    readonly version: string;
  };
  readonly rules: {
    readonly 'no-mutation': Rule.RuleModule;
  };
  readonly processors: {
    readonly wrap: Linter.Processor;
  };
  readonly configs: {
    readonly recommended: Linter.Config;
  };
};

export = plugin;
