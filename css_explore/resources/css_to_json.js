var css = require('css');

var chunks = [];

process.stdin.on('readable', function () {
    var chunk = process.stdin.read();
    if (chunk !== null) {
        chunks.push(chunk);
    }
});

process.stdin.on('end', function () {
    console.log(JSON.stringify(css.parse(Buffer.concat(chunks).toString('UTF-8'), {silent: false})));
});
