
class BackpropMode:
    """
    Back-propagation mode. Choose amongst:
        - ``BackpropMode.GRADIENT``
        - ``BackpropMode.EM``
        - ``BackpropMode.HARD_EM``
        - ``BackpropMode.HARD_EM_UNWEIGHTED``
    """

    GRADIENT = "gradient"
    HARD_EM = "hard_em"
    HARD_EM_UNWEIGHTED = "hard_em_unweighted"
    EM = "em"
