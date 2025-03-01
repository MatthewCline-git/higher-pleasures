const logger = {
  debug: (message: string, data?: any): void => {
    console.debug(`${message}`, data ? data : "");
  },
  info: (message: string, data?: any): void => {
    console.info(`${message}`, data ? data : "");
  },
  warn: (message: string, data?: any): void => {
    console.warn(`${message}`, data ? data : "");
  },
  error: (message: string, data?: any): void => {
    console.error(`${message}`, data ? data : "");
  },
  // Create a component-specific logger
  component: (componentName: string) => ({
    debug: (message: string, data?: any) =>
      logger.debug(`[${componentName}] ${message}`, data),
    info: (message: string, data?: any) =>
      logger.info(`[${componentName}] ${message}`, data),
    warn: (message: string, data?: any) =>
      logger.warn(`[${componentName}] ${message}`, data),
    error: (message: string, error?: any) =>
      logger.error(`[${componentName}] ${message}`, error),
  }),
};

export default logger;
