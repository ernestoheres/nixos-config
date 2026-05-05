return {
  trig = "dddctrl",
  name = "DDD controller endpoint",
  desc = "ASP.NET controller endpoint using ISender",
  template = [[
[ApiController]
[Route("api/[controller]")]
public sealed class {{Feature}}Controller(ISender sender) : ControllerBase
{
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<{{Response}}>> GetById(Guid id, CancellationToken ct)
    {
        var result = await sender.Send(new Get{{Feature}}Query(id), ct);
        return Ok(result);
    }
}
]],
}
