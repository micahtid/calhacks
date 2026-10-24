// Every store shares this Next.js config. Workspace packages ship TypeScript, so Next.js compiles them.
const nextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  devIndicators: false,
  transpilePackages: ["@calhacks/common", "@calhacks/amazon"],
};

export default nextConfig;
