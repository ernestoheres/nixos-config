[ApiController]
[Route("api/[controller]")]
public sealed class OrganizationController(ISender sender) : ControllerBase
{
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<Response>> GetById(Guid id, CancellationToken ct)
    {
        var result = await sender.Send(new GetOrganizationQuery(id), ct);
        return Ok(result);
    }
}


jdddquery
dddcommand
[ApiController]
[Route("api/[controller]")]
public sealed class jjjjjjjjjjjjjjjjjjjjjjjjController(ISender sender) : ControllerBase
{
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<Response>> GetById(Guid id, CancellationToken ct)
    {
        var result = await sender.Send(new GetjjjjjjjjjjjjjjjjjjjjjjjjQuery(id), ct);
        return Ok(result);
    }
}

public sealed record bruhyeeeewweweQuery(Args) : IRequest<OrderDT;

public sealed class bruhyeeeewweweFeatureQueryHandler(Dependency)
    : IRequestHandler<bruhyeeeewweweFeatureQuery, Response>
{
    public async Task<Response> Handle(bruhyeeeewweweFeatureQuery request, CancellationToken ct)
    {
        throw new NotImplementedException();
    }
}
public sealed record ewkjfewkfjewfjw:FeatureCommand(Args) : IRequest<Response>;

public sealed class ewkjfewkfjewfjw:FeatureCommandHandler(Dependency)
    : IRequestHandler<ewkjfewkfjewfjw:FeatureCommand, Response>
{
    public async Task<Response> Handle(ewkjfewkfjewfjw:FeatureCommand request, CancellationToken ct)
    {
        throw new NotImplementedException();
    }
}

