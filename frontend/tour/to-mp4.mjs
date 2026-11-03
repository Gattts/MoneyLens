// Converte o vídeo do tour (WebM do Playwright) para MP4 H.264, que toca em qualquer navegador, e tira o pôster.
// Usa o ffmpeg instalado; sem ele, a imagem Docker abaixo (baixada na primeira vez).
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const OUTPUT = path.resolve('tour-output')
const IMAGE = 'jrottenberg/ffmpeg:7.1-alpine'
const SOURCE = 'tour.webm'

if (!fs.existsSync(path.join(OUTPUT, SOURCE))) {
  console.error(`${SOURCE} não encontrado em ${OUTPUT}: rode o tour antes.`)
  process.exit(1)
}

const local = spawnSync('ffmpeg', ['-version'], { stdio: 'ignore' }).status === 0
const docker = `run --rm --user ${process.getuid()}:${process.getgid()} -v ${OUTPUT}:/data -w /data ${IMAGE}`

function ffmpeg(args) {
  const [command, prefix] = local ? ['ffmpeg', ''] : ['docker', docker]
  const line = `${prefix} -hide_banner -loglevel error -y ${args}`.trim().split(/\s+/)
  const done = spawnSync(command, line, { cwd: OUTPUT, stdio: 'inherit' })
  if (done.status !== 0) process.exit(done.status ?? 1)
}

ffmpeg(`-i ${SOURCE} -c:v libx264 -pix_fmt yuv420p -movflags +faststart -crf 28 -preset veryfast -an tour.mp4`)
// Pôster: o Painel logo antes da rolagem (a segunda parada), quando o aviso de alertas já sumiu.
const chapters = JSON.parse(fs.readFileSync(path.join(OUTPUT, 'chapters.json'), 'utf8'))
const posterAt = Math.max(0, chapters[1].at - 0.5)
ffmpeg(`-ss ${posterAt} -i ${SOURCE} -frames:v 1 -q:v 3 poster.jpg`)
fs.rmSync(path.join(OUTPUT, SOURCE))

const size = fs.statSync(path.join(OUTPUT, 'tour.mp4')).size / 1024 / 1024
console.log(`tour.mp4 (${size.toFixed(1)} MB) e poster.jpg em ${OUTPUT}`)
