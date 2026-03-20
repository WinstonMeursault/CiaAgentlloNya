from yaml import safe_load as yamlSafeLoad

with open('./config.yaml', 'r') as yamlConfig:
    botConfig = yamlSafeLoad(yamlConfig)['Nekomimi']
    