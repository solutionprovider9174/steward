const path = require('path');

module.exports = {
    mode: "development",
    entry: "./src", // string | object | array
    output: {
        path: path.resolve(__dirname, "steward/static/js"),
        filename: "bundle.js",
    },
    resolve: {
        modules: [
            "node_modules",
            path.resolve(__dirname, "src")
        ],
        extensions: [".js", ".json", ".jsx", ".css"],
    },
    performance: {
        hints: "warning",
        maxAssetSize: 200000,
        maxEntrypointSize: 400000,
        assetFilter: function (assetFilename) {
            return assetFilename.endsWith('.css') || assetFilename.endsWith('.js');
        }
    },
    devtool: "source-map",
    context: __dirname,
    target: "web",
    stats: "errors-only",
}