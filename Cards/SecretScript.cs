using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BaseLib.Abstracts;
using BaseLib.Utils;
using MegaCrit.Sts2.Core.CardSelection;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.CardPools;
using SecretScript.Extensions;

namespace SecretScript.Cards;

[Pool(typeof(ColorlessCardPool))]
public sealed class SecretScript : CustomCardModel
{
    public override IEnumerable<CardKeyword> CanonicalKeywords => [CardKeyword.Exhaust];

    public override string CustomPortraitPath => "secret_script.png".BigCardImagePath();
    public override string PortraitPath => "secret_script.png".CardImagePath();
    public override string BetaPortraitPath => "beta/secret_script.png".CardImagePath();

    public SecretScript()
        : base(0, CardType.Skill, CardRarity.Rare, TargetType.Self)
    {
    }

    protected override async Task OnPlay(PlayerChoiceContext choiceContext, CardPlay cardPlay)
    {
        CardSelectorPrefs prefs = new(SelectionScreenPrompt, 1);
        List<CardModel> cards = PileType.Draw.GetPile(Owner).Cards
            .Where(c => c.Type == CardType.Power).ToList();
        CardModel? selected = (await CardSelectCmd.FromSimpleGrid(choiceContext, cards, Owner, prefs))
            .FirstOrDefault();
        if (selected != null)
        {
            await CardPileCmd.Add(selected, PileType.Hand);
        }
    }

    protected override void OnUpgrade()
    {
        AddKeyword(CardKeyword.Innate);
    }
}
