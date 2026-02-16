from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import process_voice_command


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_command(request):
    transcript = (request.data.get("transcript") or "").strip()
    if not transcript:
        return Response({"error": "transcript is required"}, status=status.HTTP_400_BAD_REQUEST)

    result = process_voice_command(user=request.user, transcript=transcript)
    return Response(result, status=status.HTTP_200_OK)
