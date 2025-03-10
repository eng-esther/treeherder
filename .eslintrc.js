module.exports = {
  root: true,
  extends: [
    'eslint-config-airbnb',
    // We use Prettier instead of AirBnb for style-related rules (see .prettierrc.js).
    'plugin:prettier/recommended',
    // Disable React-related AirBnB style rules.
    'prettier/react',
    'plugin:jest/recommended',
    'plugin:jest/style',
  ],
  parser: 'babel-eslint',
  settings: {
    react: {
      version: '16.6',
    },
  },
  env: {
    browser: true,
  },
  globals: {
    page: true,
    browser: true,
    jestPuppeteer: true,
  },
  rules: {
    'class-methods-use-this': 'off',
    'consistent-return': 'off',
    'default-case': 'off',
    'jsx-a11y/click-events-have-key-events': 'off',
    'no-alert': 'off',
    'no-continue': 'off',
    'no-param-reassign': 'off',
    'no-plusplus': 'off',
    'no-restricted-syntax': 'off',
    'no-shadow': 'off',
    'no-underscore-dangle': 'off',
    'prefer-promise-reject-errors': 'off',
    'react/destructuring-assignment': 'off',
    'react/jsx-fragments': 'off',
    'react/jsx-props-no-spreading': 'off',
    'react/prop-types': 'off',
    'import/extensions': 'off',
    // Override AirBnB's config for this rule to make it more strict.
    // https://github.com/benmosher/eslint-plugin-import/blob/master/docs/rules/order.md
    'import/order': [
      'error',
      {
        'newlines-between': 'always',
      },
    ],
  },
};
