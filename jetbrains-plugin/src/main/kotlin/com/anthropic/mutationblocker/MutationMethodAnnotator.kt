package com.anthropic.mutationblocker

import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.BufferedReader
import java.io.InputStreamReader

data class CollectInput(val filePath: String, val text: String)

data class AnnotateResult(
    val filePath: String,
    val diagnostics: List<DiagnosticPayload>,
)

data class DiagnosticPayload(
    val line: Int,
    val character: Int,
    val endLine: Int,
    val endCharacter: Int,
    val severity: Int,
    val message: String,
    val code: String,
)

class MutationMethodAnnotator : ExternalAnnotator<CollectInput, AnnotateResult>() {
    private val json = Json { ignoreUnknownKeys = true }

    override fun collectInformation(file: PsiFile, editor: Editor, hasErrors: Boolean): CollectInput? {
        val virtualFile = file.virtualFile ?: return null
        return CollectInput(virtualFile.path, file.text)
    }

    override fun doAnnotate(input: CollectInput?): AnnotateResult? {
        val payload = input ?: return null
        val hookPath = System.getenv("MUTATION_METHOD_HOOK_PATH")
            ?: defaultHookPath()
            ?: return null
        val process = ProcessBuilder("python3", hookPath)
            .redirectErrorStream(false)
            .start()
            .apply {
                outputStream.use { stream ->
                    stream.write((payload.filePath + "\n").toByteArray(Charsets.UTF_8))
                }
            }
        val stdout = BufferedReader(InputStreamReader(process.inputStream, Charsets.UTF_8))
            .readText()
        process.waitFor()
        val parsed = runCatching { json.parseToJsonElement(stdout).jsonArray }.getOrNull()
            ?: return AnnotateResult(payload.filePath, emptyList())
        val diagnostics = parsed
            .map { it.jsonObject }
            .filter { it["uri"]?.jsonPrimitive?.contentOrNull?.endsWith(payload.filePath) == true }
            .flatMap { doc -> diagnosticsFrom(doc["diagnostics"]?.jsonArray ?: JsonArray(emptyList())) }
        return AnnotateResult(payload.filePath, diagnostics)
    }

    override fun apply(file: PsiFile, annotationResult: AnnotateResult?, holder: AnnotationHolder) {
        val result = annotationResult ?: return
        val document = file.viewProvider.document ?: return
        result.diagnostics
            .asSequence()
            .map { diag ->
                val startOffset = document.getLineStartOffset(diag.line.coerceAtMost(document.lineCount - 1)) + diag.character
                val endOffset = (document.getLineStartOffset(diag.endLine.coerceAtMost(document.lineCount - 1)) + diag.endCharacter)
                    .coerceAtLeast(startOffset + 1)
                Triple(diag, TextRange(startOffset, endOffset), severityFor(diag.severity))
            }
            .forEach { (diag, range, severity) ->
                holder.newAnnotation(severity, "[${diag.code}] ${diag.message}")
                    .range(range)
                    .needsUpdateOnTyping(true)
                    .create()
            }
    }

    private fun diagnosticsFrom(array: JsonArray): List<DiagnosticPayload> =
        array.mapNotNull { element ->
            val obj = element.jsonObject
            val range = obj["range"]?.jsonObject ?: return@mapNotNull null
            val start = range["start"]?.jsonObject ?: return@mapNotNull null
            val end = range["end"]?.jsonObject ?: start
            DiagnosticPayload(
                line = start["line"]?.jsonPrimitive?.intOrNull ?: 0,
                character = start["character"]?.jsonPrimitive?.intOrNull ?: 0,
                endLine = end["line"]?.jsonPrimitive?.intOrNull ?: 0,
                endCharacter = end["character"]?.jsonPrimitive?.intOrNull ?: 0,
                severity = obj["severity"]?.jsonPrimitive?.intOrNull ?: 2,
                message = obj["message"]?.jsonPrimitive?.contentOrNull ?: "",
                code = obj["code"]?.jsonPrimitive?.contentOrNull ?: "",
            )
        }

    private fun severityFor(severity: Int): HighlightSeverity =
        when (severity) {
            1 -> HighlightSeverity.ERROR
            2 -> HighlightSeverity.WARNING
            3 -> HighlightSeverity.WEAK_WARNING
            else -> HighlightSeverity.INFORMATION
        }

    private fun defaultHookPath(): String? =
        listOf(
            System.getProperty("user.home") + "/.claude/hooks/mutation-method-blocker.py",
        ).firstOrNull { java.io.File(it).exists() }
}
